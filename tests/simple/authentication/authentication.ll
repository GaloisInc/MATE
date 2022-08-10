; ModuleID = 'authentication.bc'
source_filename = "authentication.c"
target datalayout = "e-m:e-i64:64-f80:128-n8:16:32:64-S128"
target triple = "x86_64-pc-linux-gnu"

%struct._IO_FILE = type { i32, i8*, i8*, i8*, i8*, i8*, i8*, i8*, i8*, i8*, i8*, i8*, %struct._IO_marker*, %struct._IO_FILE*, i32, i32, i64, i16, i8, [1 x i8], i8*, i64, i8*, i8*, i8*, i8*, i64, i32, [20 x i8] }
%struct._IO_marker = type { %struct._IO_marker*, %struct._IO_FILE*, i32 }

@.str = private unnamed_addr constant [79 x i8] c"Enter 1 to read logs (requires login) and 2 to write to logs (requires admin)\0A\00", align 1
@stdin = external dso_local global %struct._IO_FILE*, align 8
@.str.1 = private unnamed_addr constant [3 x i8] c"%d\00", align 1
@.str.2 = private unnamed_addr constant [17 x i8] c"Invalid option.\0A\00", align 1
@.str.3 = private unnamed_addr constant [47 x i8] c"Successful admin login. Enter message to log:\0A\00", align 1
@.str.4 = private unnamed_addr constant [27 x i8] c"Unsuccessful admin login.\0A\00", align 1
@.str.5 = private unnamed_addr constant [51 x i8] c"Successful user login. Enter log line to display:\0A\00", align 1
@.str.6 = private unnamed_addr constant [17 x i8] c"adminLogging.txt\00", align 1
@.str.7 = private unnamed_addr constant [3 x i8] c"%s\00", align 1
@.str.8 = private unnamed_addr constant [26 x i8] c"Unsuccessful user login.\0A\00", align 1
@.str.9 = private unnamed_addr constant [2 x i8] c"r\00", align 1
@.str.10 = private unnamed_addr constant [2 x i8] c"a\00", align 1
@.str.11 = private unnamed_addr constant [16 x i8] c"credentials.txt\00", align 1
@.str.12 = private unnamed_addr constant [40 x i8] c"Hello, please log in, enter your name!\0A\00", align 1
@.str.13 = private unnamed_addr constant [22 x i8] c"Enter your password!\0A\00", align 1

; Function Attrs: noinline nounwind optnone uwtable
define dso_local i32 @main() #0 {
  %1 = alloca i32, align 4
  %2 = alloca i32, align 4
  %3 = alloca [24 x i8], align 16
  %4 = alloca i32, align 4
  store i32 0, i32* %1, align 4
  %5 = call i32 (i8*, ...) @printf(i8* getelementptr inbounds ([79 x i8], [79 x i8]* @.str, i32 0, i32 0))
  %6 = getelementptr inbounds [24 x i8], [24 x i8]* %3, i32 0, i32 0
  %7 = load %struct._IO_FILE*, %struct._IO_FILE** @stdin, align 8
  %8 = call i8* @fgets(i8* %6, i32 24, %struct._IO_FILE* %7)
  %9 = getelementptr inbounds [24 x i8], [24 x i8]* %3, i32 0, i32 0
  %10 = call i32 (i8*, i8*, ...) @__isoc99_sscanf(i8* %9, i8* getelementptr inbounds ([3 x i8], [3 x i8]* @.str.1, i32 0, i32 0), i32* %2) #5
  %11 = call i32 @credentialCheck()
  store i32 %11, i32* %4, align 4
  %12 = load i32, i32* %2, align 4
  switch i32 %12, label %28 [
    i32 1, label %13
    i32 2, label %22
  ]

; <label>:13:                                     ; preds = %0
  %14 = load i32, i32* %4, align 4
  %15 = icmp eq i32 %14, 1
  br i1 %15, label %19, label %16

; <label>:16:                                     ; preds = %13
  %17 = load i32, i32* %4, align 4
  %18 = icmp eq i32 %17, 2
  br i1 %18, label %19, label %20

; <label>:19:                                     ; preds = %16, %13
  call void @userSuccess()
  br label %21

; <label>:20:                                     ; preds = %16
  call void @userFail()
  br label %21

; <label>:21:                                     ; preds = %20, %19
  br label %30

; <label>:22:                                     ; preds = %0
  %23 = load i32, i32* %4, align 4
  %24 = icmp eq i32 %23, 2
  br i1 %24, label %25, label %26

; <label>:25:                                     ; preds = %22
  call void @adminSuccess()
  br label %27

; <label>:26:                                     ; preds = %22
  call void @adminFail()
  br label %27

; <label>:27:                                     ; preds = %26, %25
  br label %30

; <label>:28:                                     ; preds = %0
  %29 = call i32 (i8*, ...) @printf(i8* getelementptr inbounds ([17 x i8], [17 x i8]* @.str.2, i32 0, i32 0))
  br label %30

; <label>:30:                                     ; preds = %28, %27, %21
  %31 = load i32, i32* %1, align 4
  ret i32 %31
}

declare dso_local i32 @printf(i8*, ...) #1

declare dso_local i8* @fgets(i8*, i32, %struct._IO_FILE*) #1

; Function Attrs: nounwind
declare dso_local i32 @__isoc99_sscanf(i8*, i8*, ...) #2

; Function Attrs: noinline nounwind optnone uwtable
define dso_local void @adminSuccess() #0 {
  %1 = alloca [256 x i8], align 16
  %2 = load %struct._IO_FILE*, %struct._IO_FILE** @stdin, align 8
  %3 = call i32 @fflush(%struct._IO_FILE* %2)
  %4 = call i32 (i8*, ...) @printf(i8* getelementptr inbounds ([47 x i8], [47 x i8]* @.str.3, i32 0, i32 0))
  %5 = getelementptr inbounds [256 x i8], [256 x i8]* %1, i32 0, i32 0
  %6 = load %struct._IO_FILE*, %struct._IO_FILE** @stdin, align 8
  %7 = call i8* @fgets(i8* %5, i32 256, %struct._IO_FILE* %6)
  %8 = getelementptr inbounds [256 x i8], [256 x i8]* %1, i32 0, i32 0
  call void @adminFile(i8* %8)
  call void @exit(i32 0) #6
  unreachable
                                                  ; No predecessors!
  ret void
}

declare dso_local i32 @fflush(%struct._IO_FILE*) #1

; Function Attrs: noinline nounwind optnone uwtable
define dso_local void @adminFile(i8*) #0 {
  %2 = alloca i8*, align 8
  %3 = alloca %struct._IO_FILE*, align 8
  store i8* %0, i8** %2, align 8
  %4 = call %struct._IO_FILE* @fopen(i8* getelementptr inbounds ([17 x i8], [17 x i8]* @.str.6, i32 0, i32 0), i8* getelementptr inbounds ([2 x i8], [2 x i8]* @.str.10, i32 0, i32 0))
  store %struct._IO_FILE* %4, %struct._IO_FILE** %3, align 8
  %5 = load i8*, i8** %2, align 8
  %6 = load %struct._IO_FILE*, %struct._IO_FILE** %3, align 8
  %7 = call i32 @fputs(i8* %5, %struct._IO_FILE* %6)
  %8 = load %struct._IO_FILE*, %struct._IO_FILE** %3, align 8
  %9 = call i32 @fclose(%struct._IO_FILE* %8)
  ret void
}

; Function Attrs: noreturn nounwind
declare dso_local void @exit(i32) #3

; Function Attrs: noinline nounwind optnone uwtable
define dso_local void @adminFail() #0 {
  %1 = call i32 (i8*, ...) @printf(i8* getelementptr inbounds ([27 x i8], [27 x i8]* @.str.4, i32 0, i32 0))
  call void @exit(i32 1) #6
  unreachable
                                                  ; No predecessors!
  ret void
}

; Function Attrs: noinline nounwind optnone uwtable
define dso_local void @userSuccess() #0 {
  %1 = alloca [256 x i8], align 16
  %2 = alloca i32, align 4
  %3 = call i32 (i8*, ...) @printf(i8* getelementptr inbounds ([51 x i8], [51 x i8]* @.str.5, i32 0, i32 0))
  %4 = getelementptr inbounds [256 x i8], [256 x i8]* %1, i32 0, i32 0
  %5 = load %struct._IO_FILE*, %struct._IO_FILE** @stdin, align 8
  %6 = call i8* @fgets(i8* %4, i32 256, %struct._IO_FILE* %5)
  %7 = getelementptr inbounds [256 x i8], [256 x i8]* %1, i32 0, i32 0
  %8 = call i32 (i8*, i8*, ...) @__isoc99_sscanf(i8* %7, i8* getelementptr inbounds ([3 x i8], [3 x i8]* @.str.1, i32 0, i32 0), i32* %2) #5
  %9 = getelementptr inbounds [256 x i8], [256 x i8]* %1, i32 0, i32 0
  %10 = load i32, i32* %2, align 4
  call void @fileReader(i8* getelementptr inbounds ([17 x i8], [17 x i8]* @.str.6, i32 0, i32 0), i8* %9, i32 %10)
  %11 = getelementptr inbounds [256 x i8], [256 x i8]* %1, i32 0, i32 0
  %12 = call i32 (i8*, ...) @printf(i8* getelementptr inbounds ([3 x i8], [3 x i8]* @.str.7, i32 0, i32 0), i8* %11)
  call void @exit(i32 0) #6
  unreachable
                                                  ; No predecessors!
  ret void
}

; Function Attrs: noinline nounwind optnone uwtable
define dso_local void @fileReader(i8*, i8*, i32) #0 {
  %4 = alloca i8*, align 8
  %5 = alloca i8*, align 8
  %6 = alloca i32, align 4
  %7 = alloca %struct._IO_FILE*, align 8
  %8 = alloca [256 x i8], align 16
  %9 = alloca i32, align 4
  store i8* %0, i8** %4, align 8
  store i8* %1, i8** %5, align 8
  store i32 %2, i32* %6, align 4
  %10 = load i8*, i8** %4, align 8
  %11 = call %struct._IO_FILE* @fopen(i8* %10, i8* getelementptr inbounds ([2 x i8], [2 x i8]* @.str.9, i32 0, i32 0))
  store %struct._IO_FILE* %11, %struct._IO_FILE** %7, align 8
  store i32 0, i32* %9, align 4
  br label %12

; <label>:12:                                     ; preds = %27, %3
  %13 = getelementptr inbounds [256 x i8], [256 x i8]* %8, i32 0, i32 0
  %14 = load %struct._IO_FILE*, %struct._IO_FILE** %7, align 8
  %15 = call i8* @fgets(i8* %13, i32 256, %struct._IO_FILE* %14)
  %16 = icmp ne i8* %15, null
  br i1 %16, label %17, label %28

; <label>:17:                                     ; preds = %12
  %18 = load i32, i32* %9, align 4
  %19 = add nsw i32 %18, 1
  store i32 %19, i32* %9, align 4
  %20 = load i32, i32* %9, align 4
  %21 = load i32, i32* %6, align 4
  %22 = icmp eq i32 %20, %21
  br i1 %22, label %23, label %27

; <label>:23:                                     ; preds = %17
  %24 = load i8*, i8** %5, align 8
  %25 = getelementptr inbounds [256 x i8], [256 x i8]* %8, i32 0, i32 0
  %26 = call i8* @strcpy(i8* %24, i8* %25) #5
  br label %28

; <label>:27:                                     ; preds = %17
  br label %12

; <label>:28:                                     ; preds = %23, %12
  ret void
}

; Function Attrs: noinline nounwind optnone uwtable
define dso_local void @userFail() #0 {
  %1 = call i32 (i8*, ...) @printf(i8* getelementptr inbounds ([26 x i8], [26 x i8]* @.str.8, i32 0, i32 0))
  call void @exit(i32 1) #6
  unreachable
                                                  ; No predecessors!
  ret void
}

declare dso_local %struct._IO_FILE* @fopen(i8*, i8*) #1

; Function Attrs: nounwind
declare dso_local i8* @strcpy(i8*, i8*) #2

declare dso_local i32 @fputs(i8*, %struct._IO_FILE*) #1

declare dso_local i32 @fclose(%struct._IO_FILE*) #1

; Function Attrs: noinline nounwind optnone uwtable
define dso_local i32 @credentialCheck() #0 {
  %1 = alloca [24 x i8], align 16
  %2 = alloca [24 x i8], align 16
  %3 = alloca [24 x i8], align 16
  %4 = alloca [24 x i8], align 16
  %5 = alloca i32, align 4
  %6 = alloca i32, align 4
  %7 = alloca i32, align 4
  store i32 0, i32* %7, align 4
  %8 = getelementptr inbounds [24 x i8], [24 x i8]* %1, i32 0, i32 0
  call void @fileReader(i8* getelementptr inbounds ([16 x i8], [16 x i8]* @.str.11, i32 0, i32 0), i8* %8, i32 1)
  %9 = getelementptr inbounds [24 x i8], [24 x i8]* %2, i32 0, i32 0
  call void @fileReader(i8* getelementptr inbounds ([16 x i8], [16 x i8]* @.str.11, i32 0, i32 0), i8* %9, i32 2)
  %10 = call i32 (i8*, ...) @printf(i8* getelementptr inbounds ([40 x i8], [40 x i8]* @.str.12, i32 0, i32 0))
  %11 = getelementptr inbounds [24 x i8], [24 x i8]* %4, i32 0, i32 0
  %12 = getelementptr inbounds [24 x i8], [24 x i8]* %2, i32 0, i32 0
  %13 = call i64 @strlen(i8* %12) #7
  %14 = add i64 %13, 1
  %15 = trunc i64 %14 to i32
  %16 = load %struct._IO_FILE*, %struct._IO_FILE** @stdin, align 8
  %17 = call i8* @fgets(i8* %11, i32 %15, %struct._IO_FILE* %16)
  %18 = call i32 (i8*, ...) @printf(i8* getelementptr inbounds ([22 x i8], [22 x i8]* @.str.13, i32 0, i32 0))
  %19 = getelementptr inbounds [24 x i8], [24 x i8]* %3, i32 0, i32 0
  %20 = getelementptr inbounds [24 x i8], [24 x i8]* %1, i32 0, i32 0
  %21 = call i64 @strlen(i8* %20) #7
  %22 = add i64 %21, 1
  %23 = trunc i64 %22 to i32
  %24 = load %struct._IO_FILE*, %struct._IO_FILE** @stdin, align 8
  %25 = call i8* @fgets(i8* %19, i32 %23, %struct._IO_FILE* %24)
  %26 = getelementptr inbounds [24 x i8], [24 x i8]* %3, i32 0, i32 0
  %27 = getelementptr inbounds [24 x i8], [24 x i8]* %1, i32 0, i32 0
  %28 = call i32 @strcmp(i8* %26, i8* %27) #7
  store i32 %28, i32* %5, align 4
  %29 = getelementptr inbounds [24 x i8], [24 x i8]* %2, i32 0, i32 0
  %30 = getelementptr inbounds [24 x i8], [24 x i8]* %4, i32 0, i32 0
  %31 = call i32 @strcmp(i8* %29, i8* %30) #7
  store i32 %31, i32* %6, align 4
  %32 = load i32, i32* %6, align 4
  %33 = icmp ne i32 %32, 0
  br i1 %33, label %34, label %40

; <label>:34:                                     ; preds = %0
  %35 = load i32, i32* %5, align 4
  %36 = icmp ne i32 %35, 0
  br i1 %36, label %38, label %37

; <label>:37:                                     ; preds = %34
  store i32 1, i32* %7, align 4
  br label %39

; <label>:38:                                     ; preds = %34
  store i32 0, i32* %7, align 4
  br label %39

; <label>:39:                                     ; preds = %38, %37
  br label %50

; <label>:40:                                     ; preds = %0
  %41 = load i32, i32* %6, align 4
  %42 = icmp ne i32 %41, 0
  br i1 %42, label %49, label %43

; <label>:43:                                     ; preds = %40
  %44 = load i32, i32* %5, align 4
  %45 = icmp ne i32 %44, 0
  br i1 %45, label %46, label %47

; <label>:46:                                     ; preds = %43
  store i32 2, i32* %7, align 4
  br label %48

; <label>:47:                                     ; preds = %43
  store i32 0, i32* %7, align 4
  br label %48

; <label>:48:                                     ; preds = %47, %46
  br label %49

; <label>:49:                                     ; preds = %48, %40
  br label %50

; <label>:50:                                     ; preds = %49, %39
  %51 = load i32, i32* %7, align 4
  ret i32 %51
}

; Function Attrs: nounwind readonly
declare dso_local i64 @strlen(i8*) #4

; Function Attrs: nounwind readonly
declare dso_local i32 @strcmp(i8*, i8*) #4

attributes #0 = { noinline nounwind optnone uwtable "correctly-rounded-divide-sqrt-fp-math"="false" "disable-tail-calls"="false" "less-precise-fpmad"="false" "no-frame-pointer-elim"="true" "no-frame-pointer-elim-non-leaf" "no-infs-fp-math"="false" "no-jump-tables"="false" "no-nans-fp-math"="false" "no-signed-zeros-fp-math"="false" "no-trapping-math"="false" "stack-protector-buffer-size"="8" "target-cpu"="x86-64" "target-features"="+fxsr,+mmx,+sse,+sse2,+x87" "unsafe-fp-math"="false" "use-soft-float"="false" }
attributes #1 = { "correctly-rounded-divide-sqrt-fp-math"="false" "disable-tail-calls"="false" "less-precise-fpmad"="false" "no-frame-pointer-elim"="true" "no-frame-pointer-elim-non-leaf" "no-infs-fp-math"="false" "no-nans-fp-math"="false" "no-signed-zeros-fp-math"="false" "no-trapping-math"="false" "stack-protector-buffer-size"="8" "target-cpu"="x86-64" "target-features"="+fxsr,+mmx,+sse,+sse2,+x87" "unsafe-fp-math"="false" "use-soft-float"="false" }
attributes #2 = { nounwind "correctly-rounded-divide-sqrt-fp-math"="false" "disable-tail-calls"="false" "less-precise-fpmad"="false" "no-frame-pointer-elim"="true" "no-frame-pointer-elim-non-leaf" "no-infs-fp-math"="false" "no-nans-fp-math"="false" "no-signed-zeros-fp-math"="false" "no-trapping-math"="false" "stack-protector-buffer-size"="8" "target-cpu"="x86-64" "target-features"="+fxsr,+mmx,+sse,+sse2,+x87" "unsafe-fp-math"="false" "use-soft-float"="false" }
attributes #3 = { noreturn nounwind "correctly-rounded-divide-sqrt-fp-math"="false" "disable-tail-calls"="false" "less-precise-fpmad"="false" "no-frame-pointer-elim"="true" "no-frame-pointer-elim-non-leaf" "no-infs-fp-math"="false" "no-nans-fp-math"="false" "no-signed-zeros-fp-math"="false" "no-trapping-math"="false" "stack-protector-buffer-size"="8" "target-cpu"="x86-64" "target-features"="+fxsr,+mmx,+sse,+sse2,+x87" "unsafe-fp-math"="false" "use-soft-float"="false" }
attributes #4 = { nounwind readonly "correctly-rounded-divide-sqrt-fp-math"="false" "disable-tail-calls"="false" "less-precise-fpmad"="false" "no-frame-pointer-elim"="true" "no-frame-pointer-elim-non-leaf" "no-infs-fp-math"="false" "no-nans-fp-math"="false" "no-signed-zeros-fp-math"="false" "no-trapping-math"="false" "stack-protector-buffer-size"="8" "target-cpu"="x86-64" "target-features"="+fxsr,+mmx,+sse,+sse2,+x87" "unsafe-fp-math"="false" "use-soft-float"="false" }
attributes #5 = { nounwind }
attributes #6 = { noreturn nounwind }
attributes #7 = { nounwind readonly }

!llvm.module.flags = !{!0}
!llvm.ident = !{!1}

!0 = !{i32 1, !"wchar_size", i32 4}
!1 = !{!"clang version 7.0.0-3~ubuntu0.18.04.1 (tags/RELEASE_700/final)"}
