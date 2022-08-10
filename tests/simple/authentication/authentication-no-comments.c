#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define STRLEN	24
#define CREDENTIALFILE "credentials.txt"
#define LOGFILE "adminLogging.txt"

enum Status{
	FAIL, USER, ADMIN
};

void adminSuccess();
void adminFail();
void userSuccess();
void userFail();
void fileReader(char* filename, char* output, int lineNum);
void adminFile(char* input);
enum Status credentialCheck();

int main(){
	/*
	 * This program is intended to model an application containing improperly
	 * implemented authentication. The comments in this version explaining the error have been removed 
     * for the purposes of blind testing - see authentication.c for an explanation of the
     * intentionally-placed vulnerabilities of this code.
	 */
	
	
	int menuChoice;
	char buff[STRLEN];
	enum Status loginStatus;
	printf("Enter 1 to read logs (requires login) and 2 to write to logs (requires admin)\n");
	fgets(buff, sizeof(buff), stdin);
	sscanf(buff, "%d", &menuChoice);
	loginStatus = credentialCheck();
	switch(menuChoice){
		case 1:
			if(loginStatus == USER || loginStatus == ADMIN){
				userSuccess();
			} else {
				userFail();
			}
			break;
		case 2:
			if(loginStatus == ADMIN){
				adminSuccess();
			} else {
				adminFail();
			}
			break;
		default:
			printf("Invalid option.\n");
			break;
	}
}

void adminSuccess(){
	//allow for appending log files
	char logMessage[256];
	fflush(stdin);
	printf("Successful admin login. Enter message to log:\n");
	fgets(logMessage, 256, stdin); 
	adminFile(logMessage);	
	exit(0);
}
void adminFail(){
	//exit
	printf("Unsuccessful admin login.\n");
	exit(1);
}
void userSuccess(){
	char buff[256];
	int lineToRead;

	printf("Successful user login. Enter log line to display:\n");
	fgets(buff, sizeof(buff), stdin);
	sscanf(buff, "%d", &lineToRead);
	fileReader(LOGFILE, buff, lineToRead);
	printf("%s", buff);
	exit(0);
}
void userFail(){
	//exit
	printf("Unsuccessful user login.\n");
	exit(1);
}
// Reads a particular line from a file.
void fileReader(char* filename, char* output, int lineNum){
	FILE* file = fopen(filename, "r");
	char line[256];
	int i = 0;
	while(fgets(line, sizeof(line), file)){
		i++;
		if(i == lineNum){
			strcpy(output, line);
			return;		
		}
	}
}
// Does admin log operations - writes (append) to log.
void adminFile(char* input){
	FILE* file = fopen(LOGFILE, "a");
	fputs(input, file);
	fclose(file);
}

enum Status credentialCheck(){
	
	char password[STRLEN];
	char adminName[STRLEN];
	char userGuess[STRLEN];
	char name[STRLEN];
	int success;
	int admin;
	enum Status loginStatus = FAIL;
	fileReader(CREDENTIALFILE, password, 1);
	fileReader(CREDENTIALFILE, adminName, 2);
	printf("Hello, please log in, enter your name!\n");
	fgets(name, strlen(adminName)+1, stdin);
	printf("Enter your password!\n");
	fgets(userGuess, strlen(password)+1, stdin);

	success = strcmp(userGuess, password);
	admin = strcmp(adminName, name);
	
	if(admin){ 
		if(!success){
			loginStatus = USER;
		} else {
			loginStatus = FAIL;
		}
	} else if(!admin){ 
		if(success){   
			loginStatus = ADMIN;
		} else {
			loginStatus = FAIL;
		}
	}
	return loginStatus;
}
