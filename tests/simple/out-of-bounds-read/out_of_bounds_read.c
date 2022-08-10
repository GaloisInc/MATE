#include <stdio.h>

void test(){
	char secret[] = "Secret found!";
	char buffer[5];
	int printLen;
	fgets(buffer, sizeof(buffer), stdin);
	printf("Enter how much to print\n");
	scanf("%d", &printLen);
	for(int i = 0; i<printLen; i++){
		putchar(buffer[i]);
	}
}
int main(int argc, char **argv){
	test();
	return 0;
}
