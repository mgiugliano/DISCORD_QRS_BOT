# Reverse Beacon Network DISCORD BOT
#
#
# Nov 3rd-8th 2022 - Michele GIUGLIANO (iv3ifz), mgiugliano@gmailcom
#
# Largely based on the 'background_task.py' example from
# https://github.com/Rapptz/discord.py/blob/master/examples/background_task.py
#
# Install Rapptz's discord.py BOT library as:
# pip3 install discord.py (or python3 -m pip install -U "discord.py[voice]")
# pip3 install call_to_dxcc

import discord      # Rapptz's discord.py BOT library
from discord.ext import commands
import call_to_dxcc # Lib to get country & continent from a (ham) call sign
import asyncio      # Python asynchronous frameworks
import time         # Time and date stamping
import datetime     # Time/date conversion (e.g. into unix-time)

from config_private import *        # Import private credentials (prefs.py)

from subprocess import PIPE, Popen  # Library for spawning a process
from threading  import Thread       # Library for running a process in background
from queue import Queue, Empty      # Library for creating a queue

# Lifetime [sec] of the spots on Discord
LIFETIME = 3 * 60       # 3 minutes

# Full path location of 'rbn_cw' and max WPM to filter in
RBNCLIENT = './rbn_cw'
MAXWPM = '20'

icons = {'EU': '🔵', 'NA': '🔴', 'SA': '⭕',
         'AF': '🟣', 'AN': '🟤', 'AS': '🟢', 'OC': '🟡'}

LEGEND = '\n*Legend*: de EU🔵, NA🔴, SA⭕, AS🟢, AF🟣, AN🟤, OC🟡\n📣 **Available for a QSO?** Send *!help* to the BOT to announce yourself.\n'


# Global variables
msgslist = []   # List of messages (for later removal)
msgstime = []   # List of messages time stamps (for later removal)
SPOT     = ''   # "buffer" containing all the spots


#-------------------------------------------------------------------------------
# Function for the asynchronous and non-blocking reading of the stdout of rbn_cw
def enqueue_output(out, queue):
    for line in iter(out.readline, b''):
        queue.put(line)
    out.close()
#-------------------------------------------------------------------------------


#-------------------------------------------------------------------------------
# Function to remove duplicate CALLS in the (SPOT) string
def remove_dup(SPOT):
    seen = set()
    answer = []

    for line in SPOT.splitlines():
        if len(line) > 1:               # Only if full (not just '\n')
            tmp = line.split('\u3000')  # Parse it by splitting at long-spaces
            call = tmp[1]               # Get the spotted call sign

            if call not in seen:        # Only if NOT repeated
            #if line not in seen:
            #    seen.add(line)
                seen.add(call)          # Add the current call sign
                answer.append(line)     # Append the **entire** line

    return '\n'.join(answer)            # Return SPOT, without "duplicates"
#-------------------------------------------------------------------------------


#-------------------------------------------------------------------------------
# Function to associate an "icon" to the continent of the spotter
def spotter_continent(DE):
    try:    # Get continent of the spotter
        _, continent, _ = call_to_dxcc.data_for_call(DE)
        try:
            icon = icons[continent]
        except KeyError:
            icon = "◯"
    except call_to_dxcc.DxccUnknownException:
        continent = '  '         # Unknown continent
        icon = "◯"               # Unknown continent icon

    return icon
#-------------------------------------------------------------------------------


#-------------------------------------------------------------------------------
# Function to prepare the (SPOT) string to send to Discord by the BOT
def prepare_spot(line, SPOT):
    # note: the (new) format of incoming line is:  "W8WTS_WD5GRW_21036.9_26"
    line = line.decode('utf-8')     # We convert the string into utf-8
    tmp  = line.split('_')           # and apply "split" by the separator '_'
    DE   = tmp[0]          # this is HA6PX  (the spotter)
    CALL = tmp[1]          # this is HB9IIH (the spotted station)
    FREQ = tmp[2]          # this is 3534.0 (the frequency in kHz)
    WPM  = tmp[3]          # this is 26     (the WPM)
    WPM  = WPM[:-1]        # The last character is a new line and I remove it

    icon = spotter_continent(DE) # the colored 'icon'     #🔴🟢⚪⚫🟣

    # We finally add an entry to the current (SPOT) string...
    # note on Discord's Markdown syntax: http://websdr.ewi.utwente.nl:8901/?tune=14042.0cw
    SPOT = f"{SPOT}\n{icon} [{FREQ} kHz](http://websdr.ewi.utwente.nl:8901/?tune={FREQ}cw)　{CALL}　{WPM}wpm"
    return SPOT
#-------------------------------------------------------------------------------

#-------------------------------------------------------------------------------
# Function to check whether a string is a (float) number or not
def is_number(s):
    try:
        float(s)
        return True
    except ValueError:
        return False
#-------------------------------------------------------------------------------


#-------------------------------------------------------------------------------
# Initialization of the BOT (i.e. called "Client")
class MyClient(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def setup_hook(self) -> None:
        # create the background tasks and run them in the background
        self.bg_task1 = self.loop.create_task(self.rbn_task())
        self.bg_task2 = self.loop.create_task(self.spot_task())
        self.bg_task3 = self.loop.create_task(self.cleanup_task())
        self.bg_task4 = self.loop.create_task(self.print_legend())

    async def on_ready(self):
        print(f'BOT has logged in as {self.user} (ID: {self.user.id})')
        print('------')

    async def on_message(self, message):
        global SPOT              # Global var
        if  message.content.startswith('!help'):
            channel = self.get_channel(SKEDCHANNEL)  # channel ID goes here
            await message.channel.send('Comand: *!sked*, followed by **freq** **call** **wpm**')
            await message.channel.send('example: *!sked* 28050.0 IV3ZZZ 15')

        elif  message.content.startswith('!sked'):
            line = message.content
            tmp = line.split(' ')
            if len(tmp) == 4:
                FREQ = tmp[1]
                CALL = tmp[2]
                CALL = CALL.upper()
                WPM  = tmp[3]
                if is_number(FREQ) and is_number(WPM) and CALL.isalnum():
                    SPOT = f"{SPOT}\n💚💚💚💚 **[{FREQ} kHz](http://websdr.ewi.utwente.nl:8901/?tune={FREQ}cw)　{CALL}　{WPM}wpm**"
                    await message.channel.send('OK!')
                else:
                    await message.channel.send('Error!')

        elif message.content.startswith('!!deleteall'):
            temp = []
            channel = self.get_channel(SKEDCHANNEL)  # channel ID goes here
            # [await message.delete() async for message in channel.history(limit=100)]
            async for message in channel.history():
                temp.append(message)
            tmp1 = await channel.send(f'MAINTENANCE: deleting {len(temp)} old messages...')
            for m in reversed(temp):
                await m.delete()
                time.sleep(1)

            await tmp1.delete()

# This function prints the 'legend', every now and then
    async def print_legend(self):
        global msgslist          # Global var 'list': referred to & modified
        global msgstime          # Global var 'list': referred to & modified

        await self.wait_until_ready()
        while not self.is_closed():
            ms = datetime.datetime.now()
            t = time.mktime(ms.timetuple()) # unix-time in seconds
            channel = self.get_channel(SKEDCHANNEL)  # channel ID goes here
            msg = await channel.send(LEGEND)
            msgslist.append(msg)
            msgstime.append(t)
            await asyncio.sleep(120)  # task runs every 1 seconds

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
# This function 'fetches' the (stdout) stream from rbn_cw executable
    async def rbn_task(self):
        global SPOT              # Global var
        global p                 # Global var
        global q                 # Global var
        global t                 # Global var

        await self.wait_until_ready()
        while not self.is_closed():
            # The Telnet client for RBN may "die" in case of TIMEOUT
            # (i.e. 60s of no incoming message from the server)
            myProcessIsRunning = p.poll() is None
            if (not myProcessIsRunning):        # If this happens...
                p = Popen([RBNCLIENT, USR, MAXWPM], stdout=PIPE, bufsize=-1, close_fds=True)
                q = Queue()
                t = Thread(target=enqueue_output, args=(p.stdout, q))
                t.daemon = True # thread dies with the program
                t.start()       # We relaunch the job.

            try:  line = q.get_nowait()     # or q.get(timeout=.1)
            except Empty:
                pass # nop
                #print('no output yet')
            else: # got line
                #print(line)
                SPOT = prepare_spot(line, SPOT) # ... do something with line
                #print(SPOT)
            await asyncio.sleep(1)  # task runs every 1 seconds

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    async def spot_task(self):
        global msgslist          # Global var 'list': referred to & modified
        global msgstime          # Global var 'list': referred to & modified
        global SPOT              # Global var

        await self.wait_until_ready()
        channel = self.get_channel(SKEDCHANNEL)  # channel ID goes here
        #mgs = [await message.delete() async for message in channel.history(limit=100)]
        # async for message in channel.history():
        #     await message.delete()
        #     time.sleep(1)

        while not self.is_closed():

            if len(SPOT) > 1:
                ms = datetime.datetime.now()
                t = time.mktime(ms.timetuple()) # unix-time in seconds

                embed = discord.Embed(title = '📡 **' + ms.strftime("%H:%M:%S") + '**', description = "", color = discord.Colour.purple())

                if len(SPOT) < 1024:  # I discard the "package" if too long.
                    SPOT = remove_dup(SPOT)
                    embed.add_field(name = "\u200b", value = SPOT, inline = True)
                    msg = await channel.send(embed=embed)
                    msgslist.append(msg)
                    msgstime.append(t)

                SPOT = ''

            await asyncio.sleep(10)  # task runs every 15 seconds

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    async def cleanup_task(self):   # Task for deleting old messages
        global msgslist          # Global var 'list': referred to & modified
        global msgstime          # Global var 'list': referred to & modified
        await self.wait_until_ready()
        while not self.is_closed():
            if len(msgslist) > 0:                # Only if list not empty...
                ms = datetime.datetime.now()     # Get the current date/time
                t  = time.mktime(ms.timetuple()) # convert into unix-time (in s)
                t0 = msgstime[0]                 # Extract the (oldest) time stamp

                if ((t - t0) >= LIFETIME):       # How much time elapsed?
                    msg = msgslist.pop(0)        # If above LIFETIME, then
                    try:
                        await msg.delete()       # get the message id and delete it
                    except:
                        pass
                    msgstime.pop(0)              # and remove it from the queues

            await asyncio.sleep(5)  # task runs every 5s (more often than the other)
#-------------------------------------------------------------------------------

#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
if __name__ == "__main__":
    p = Popen([RBNCLIENT, USR, MAXWPM], stdout=PIPE, bufsize=-1, close_fds=True)
    q = Queue()
    t = Thread(target=enqueue_output, args=(p.stdout, q))
    t.daemon = True # thread dies with the program
    t.start()

    client = MyClient(intents=discord.Intents.default())
    client.run(TOKEN)
