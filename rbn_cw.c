//
// Reverse Beacon Network CW Filter / Minimal Telnet Client
//
// 1,8 Nov 2022 - Michele GIUGLIANO (iv3ifz)
//
// Largely based on clientprog.c (a stream socket client demo)
// found at https://www.tenouk.com/Module40c.html
//
// Compile with: gcc -o rbn_cw rbn_cw.c -O
//

//#define DEBUG             // defined for extra diagnostics on screen
#define TIMEOUT 60          // Default timeout [s] - after that the program exits!

#define HOSTNAME "telnet.reversebeacon.net"
#define PORT 7000           // Port we will be connecting to (for CW spots)
//#define SIGNIN "iv3ifz\r"   // Call sign to use for RNB logging (please change it to your real callsign)

#define MAXDATASIZE 100     // Max num of bytes (i.e. characters) for the buffer

// Include of libraries
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/time.h>
#include <string.h>
#include <netdb.h>
#include <sys/types.h>
#include <netinet/in.h>
#include <sys/socket.h>

// Global variables
char tmp;               // Temporary variable storing one char at the time
char line[MAXDATASIZE]; // Max 100 chars per line
char buf[MAXDATASIZE];  // Buffer for generic socket read operation
int timeout;            // Boolean variable for the timeout condition
int retcode;            // Return code for checking errors..
int i, sockfd, numbytes;// Counter and  other useful variables
struct hostent *he;     //
struct sockaddr_in their_addr;  // connector’s address information
struct timeval tv;      //

// Interesting data extracted from each spot
char CALL[20];          // Spotted call sign      (e.g. IK3CSX)
char oldCALL[20];       // Last spotted call sign (e.g. IK3CSX)
char DE[20];            // Spotter                (e.g. MM0ZBH-#)
char FREQ[20];          // Frequency [Hz]         (e.g. 14050.9)
char MODE[10];          // Mode 				  (e.g. CW, RTTY, FT8)
char TYPE[10];          // Type 			 	  (e.g. CQ, BEACON, etc.)
int WPM;                // Spotted WPM 			  (e.g. 20, 15, 10)
int maxWPM = 20;        // Max WPM to accept - default 20 WPM (THIS IS OUR QRS FILTERING!)
char SIGNIN[10];           // Call sign to use for RNB logging (please use your real callsign)

//------------------------------------------------------------------------------
// This is the main "filtering" function, processing the data stream from RBN
void process(char *line, int maxWPM) {
    const char *delimiters = " \t\n";   // Required for strsep()
    char *field;                        // Required for 'line' parsing...
    char parsed[15][50];                // Required for 'line' parsing...
    int count = 0;                      // Required for 'line' parsing...

    #ifdef DEBUG
    printf("> %s\n", line); 			// if DEBUG, prints the "raw" line
    //printf(".");
    #endif

    // Parsing of the content/structure of the current line...
    while( (field = strsep(&line, delimiters)) != NULL ) {
        if( *field == '\0' ) { // Multiple spaces show up as empty fields.
            continue;          // Let's skip them!
        }
        strcpy(parsed[count++], field); // non-empty fields are parsed/extracted
    } // end while

    // Extraction of information...
    if (strcmp(parsed[0], "DX")==0) {       // Proceed only if it's a spot.
        if (strcmp(parsed[5], "CW")==0) {   // Then test for a 'CW' spot.
            strcpy(DE,   parsed[2]);        // Extract the relevant information
			DE[strlen(DE)-3] = '\0';
            strcpy(FREQ, parsed[3]);
            strcpy(CALL, parsed[4]);
            WPM = atoi(parsed[8]);          // Including the WPM, as integer...
            strcpy(TYPE, parsed[10]);       // TYPE could be 'BEACON' or 'CQ'

            if (strcmp(TYPE, "CQ")==0 && WPM <= maxWPM && strcmp(CALL, oldCALL)!=0) {
                strcpy(oldCALL, CALL);  // I reduce the chance of duplicates, immediately occurring.
                #ifdef DEBUG
                printf("CW: %s at %d WPM, on %s\n", CALL, WPM, FREQ);
                #endif
                //fprintf(stdout, "%s>%s@%s[%d]\n", DE, CALL, FREQ, WPM);
                fprintf(stdout, "%s_%s_%s_%d\n", DE, CALL, FREQ, WPM);
				fflush(stdout);
            } // end if CQ
        } // end if CW
    } // end if DX
    return;
} // end process()
//------------------------------------------------------------------------------


//------------------------------------------------------------------------------
int main(int argc, char *argv[]) {

    if (argc < 2) {
		fprintf(stdout, "USAGE: %s CALLSIGN [maxWPM]\n", argv[0]);
		return -1;
    }


    if (argc == 2) {
        maxWPM = 20.;
		sprintf(SIGNIN, "%s\r", argv[1]);
    }


	if (argc > 2) {
		sprintf(SIGNIN, "%s\r", argv[1]);
        maxWPM = atoi(argv[2]);
    }

    he=gethostbyname(HOSTNAME);
    sockfd = socket(AF_INET, SOCK_STREAM, 0);
    their_addr.sin_family = AF_INET;
    their_addr.sin_port = htons(PORT);
    their_addr.sin_addr = *((struct in_addr *)he->h_addr);
    memset(&(their_addr.sin_zero), '\0', 8);

    // Setting of TIMEOUT as a socket operation option..
    tv.tv_sec = TIMEOUT;        // in seconds
    tv.tv_usec = 0;             // microseconds are set to 0
    retcode = setsockopt(sockfd, SOL_SOCKET, SO_RCVTIMEO, (const char*)&tv, sizeof tv);
    if (retcode == -1) {exit(1);}

    // Connection is attempted...
    retcode = connect(sockfd, (struct sockaddr *)&their_addr, sizeof(struct sockaddr));
    if (retcode == -1) {exit(1);}

    // Reading the incoming input stream is attempted...
    numbytes = recv(sockfd, buf, MAXDATASIZE-1, 0);
    if (numbytes == 0) {exit(1);}
    buf[numbytes] = '\0';
    #ifdef DEBUG
    printf(">>>%s\n", buf);
    #endif

    // Response with the SIGNIN call sign, to "log on"...
    numbytes = send(sockfd, SIGNIN, strlen(SIGNIN), 0);
    if (numbytes != strlen(SIGNIN)) {exit(1);}
    #ifdef DEBUG
    printf("<<<%s\n", SIGNIN);
    #endif

    // Now we are "in"....
    //--- MAIN (INFINITE) LOOP STARTS HERE -------------------------------------
    i = 0;                          // Init of the counter over "line" chars.
    timeout = 0;                    // Init as "no timeout occurred (yet)"

    while (!timeout) {                        // Read one char at the time...
        numbytes = recv(sockfd, &tmp, 1, 0);  // into the 'tmp' variable.

        if (numbytes == 1) {                // At least one char was indeed read.

            if (tmp == '\n') {              // If new line char, line is over!
                line[i++] = '\0';           // Every string in C ends with '\0'

                process(line, maxWPM);      // Process the line

                i = 0;                      // then reset the counter..
                line[0] = '\0';             // String "deleted".
                }
            else {                          // Otherwise, simply append one
                line[i++] = tmp;            // new char to the current line...
                }

        }
        else {// (numbytes == 0)            // Timeout occurred!
            timeout = 1;
            #ifdef DEBUG
            printf("TIMEOUT!\n");
            #endif
        } // if
    } // while

    // We can only return because of a timeout!
	// If that happens, let's do things properly (i.e. closing the socket and returning 0)
close(sockfd);
return 0;
} // end main()
//------------------------------------------------------------------------------