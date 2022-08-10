; ModuleID = 'jupyter/examples/assets/guessing-game.bc'
source_filename = "llvm-link"
target datalayout = "e-m:e-p270:32:32-p271:32:32-p272:64:64-i64:64-f80:128-n8:16:32:64-S128"
target triple = "x86_64-unknown-linux-gnu"

%struct.secret = type { i32 }

@hidden = common dso_local global %struct.secret zeroinitializer, align 4, !dbg !0
@.str = private unnamed_addr constant [28 x i8] c"You win! the secret was %d\0A\00", align 1
@.str.1 = private unnamed_addr constant [15 x i8] c"Wrong answer!\0A\00", align 1
@.str.2 = private unnamed_addr constant [31 x i8] c"You're out of guesses, sorry.\0A\00", align 1
@.str.6 = private unnamed_addr constant [21 x i8] c"Your guesses so far:\00", align 1
@.str.7 = private unnamed_addr constant [4 x i8] c" %d\00", align 1
@.str.8 = private unnamed_addr constant [2 x i8] c"\0A\00", align 1
@.str.4 = private unnamed_addr constant [22 x i8] c"Guess a number 1-10: \00", align 1
@.str.5 = private unnamed_addr constant [27 x i8] c"Invalid entry. Try again.\0A\00", align 1
@.str.3 = private unnamed_addr constant [3 x i8] c"%d\00", align 1

; Function Attrs: noinline nounwind optnone uwtable
define dso_local i32 @main() #0 !dbg !15 {
  %1 = alloca i32, align 4
  %2 = alloca i32*, align 8
  %3 = alloca i32, align 4
  store i32 0, i32* %1, align 4
  %4 = call i32 @rand() #4, !dbg !18
  %5 = srem i32 %4, 10, !dbg !19
  %6 = add nsw i32 %5, 1, !dbg !20
  store i32 %6, i32* getelementptr inbounds (%struct.secret, %struct.secret* @hidden, i32 0, i32 0), align 4, !dbg !21
  call void @llvm.dbg.declare(metadata i32** %2, metadata !22, metadata !DIExpression()), !dbg !24
  %7 = call noalias i8* @calloc(i64 9, i64 4) #4, !dbg !25
  %8 = bitcast i8* %7 to i32*, !dbg !25
  store i32* %8, i32** %2, align 8, !dbg !24
  call void @llvm.dbg.declare(metadata i32* %3, metadata !26, metadata !DIExpression()), !dbg !28
  store i32 0, i32* %3, align 4, !dbg !28
  br label %9, !dbg !29

9:                                                ; preds = %34, %0
  %10 = load i32, i32* %3, align 4, !dbg !30
  %11 = icmp slt i32 %10, 9, !dbg !32
  br i1 %11, label %12, label %37, !dbg !33

12:                                               ; preds = %9
  %13 = load i32*, i32** %2, align 8, !dbg !34
  %14 = load i32, i32* %3, align 4, !dbg !36
  %15 = sext i32 %14 to i64, !dbg !34
  %16 = getelementptr inbounds i32, i32* %13, i64 %15, !dbg !34
  call void @get_guess(i32* %16), !dbg !37
  %17 = load i32*, i32** %2, align 8, !dbg !38
  %18 = load i32, i32* %3, align 4, !dbg !40
  %19 = sext i32 %18 to i64, !dbg !38
  %20 = getelementptr inbounds i32, i32* %17, i64 %19, !dbg !38
  %21 = load i32, i32* %20, align 4, !dbg !38
  %22 = load i32, i32* getelementptr inbounds (%struct.secret, %struct.secret* @hidden, i32 0, i32 0), align 4, !dbg !41
  %23 = icmp eq i32 %21, %22, !dbg !42
  br i1 %23, label %24, label %29, !dbg !43

24:                                               ; preds = %12
  %25 = load i32, i32* getelementptr inbounds (%struct.secret, %struct.secret* @hidden, i32 0, i32 0), align 4, !dbg !44
  %26 = call i32 (i8*, ...) @printf(i8* getelementptr inbounds ([28 x i8], [28 x i8]* @.str, i64 0, i64 0), i32 %25), !dbg !46
  %27 = load i32*, i32** %2, align 8, !dbg !47
  %28 = bitcast i32* %27 to i8*, !dbg !47
  call void @free(i8* %28) #4, !dbg !48
  store i32 0, i32* %1, align 4, !dbg !49
  br label %41, !dbg !49

29:                                               ; preds = %12
  %30 = call i32 (i8*, ...) @printf(i8* getelementptr inbounds ([15 x i8], [15 x i8]* @.str.1, i64 0, i64 0)), !dbg !50
  %31 = load i32*, i32** %2, align 8, !dbg !52
  %32 = load i32, i32* %3, align 4, !dbg !53
  call void @print_guesses(i32* %31, i32 %32), !dbg !54
  br label %33

33:                                               ; preds = %29
  br label %34, !dbg !55

34:                                               ; preds = %33
  %35 = load i32, i32* %3, align 4, !dbg !56
  %36 = add nsw i32 %35, 1, !dbg !56
  store i32 %36, i32* %3, align 4, !dbg !56
  br label %9, !dbg !57, !llvm.loop !58

37:                                               ; preds = %9
  %38 = call i32 (i8*, ...) @printf(i8* getelementptr inbounds ([31 x i8], [31 x i8]* @.str.2, i64 0, i64 0)), !dbg !60
  %39 = load i32*, i32** %2, align 8, !dbg !61
  %40 = bitcast i32* %39 to i8*, !dbg !61
  call void @free(i8* %40) #4, !dbg !62
  store i32 -1, i32* %1, align 4, !dbg !63
  br label %41, !dbg !63

41:                                               ; preds = %37, %24
  %42 = load i32, i32* %1, align 4, !dbg !64
  ret i32 %42, !dbg !64
}

; Function Attrs: nounwind
declare dso_local i32 @rand() #1

; Function Attrs: nounwind readnone speculatable willreturn
declare void @llvm.dbg.declare(metadata, metadata, metadata) #2

; Function Attrs: nounwind
declare dso_local noalias i8* @calloc(i64, i64) #1

; Function Attrs: noinline nounwind optnone uwtable
define dso_local void @get_guess(i32* %0) #0 !dbg !65 {
  %2 = alloca i32*, align 8
  store i32* %0, i32** %2, align 8
  call void @llvm.dbg.declare(metadata i32** %2, metadata !68, metadata !DIExpression()), !dbg !69
  %3 = call i32 (i8*, ...) @printf(i8* getelementptr inbounds ([22 x i8], [22 x i8]* @.str.4, i64 0, i64 0)), !dbg !70
  br label %4, !dbg !71

4:                                                ; preds = %1, %11
  %5 = load i32*, i32** %2, align 8, !dbg !72
  %6 = call i32 @read_num(i32* %5), !dbg !75
  %7 = icmp eq i32 %6, 0, !dbg !76
  br i1 %7, label %8, label %9, !dbg !77

8:                                                ; preds = %4
  ret void, !dbg !78

9:                                                ; preds = %4
  %10 = call i32 (i8*, ...) @printf(i8* getelementptr inbounds ([27 x i8], [27 x i8]* @.str.5, i64 0, i64 0)), !dbg !80
  br label %11

11:                                               ; preds = %9
  br label %4, !dbg !71, !llvm.loop !82
}

declare dso_local i32 @printf(i8*, ...) #3

; Function Attrs: nounwind
declare dso_local void @free(i8*) #1

; Function Attrs: noinline nounwind optnone uwtable
define dso_local void @print_guesses(i32* %0, i32 %1) #0 !dbg !84 {
  %3 = alloca i32*, align 8
  %4 = alloca i32, align 4
  %5 = alloca i32, align 4
  store i32* %0, i32** %3, align 8
  call void @llvm.dbg.declare(metadata i32** %3, metadata !87, metadata !DIExpression()), !dbg !88
  store i32 %1, i32* %4, align 4
  call void @llvm.dbg.declare(metadata i32* %4, metadata !89, metadata !DIExpression()), !dbg !90
  %6 = call i32 (i8*, ...) @printf(i8* getelementptr inbounds ([21 x i8], [21 x i8]* @.str.6, i64 0, i64 0)), !dbg !91
  call void @llvm.dbg.declare(metadata i32* %5, metadata !92, metadata !DIExpression()), !dbg !94
  store i32 0, i32* %5, align 4, !dbg !94
  br label %7, !dbg !95

7:                                                ; preds = %18, %2
  %8 = load i32, i32* %5, align 4, !dbg !96
  %9 = load i32, i32* %4, align 4, !dbg !98
  %10 = icmp sle i32 %8, %9, !dbg !99
  br i1 %10, label %11, label %21, !dbg !100

11:                                               ; preds = %7
  %12 = load i32*, i32** %3, align 8, !dbg !101
  %13 = load i32, i32* %5, align 4, !dbg !103
  %14 = sext i32 %13 to i64, !dbg !101
  %15 = getelementptr inbounds i32, i32* %12, i64 %14, !dbg !101
  %16 = load i32, i32* %15, align 4, !dbg !101
  %17 = call i32 (i8*, ...) @printf(i8* getelementptr inbounds ([4 x i8], [4 x i8]* @.str.7, i64 0, i64 0), i32 %16), !dbg !104
  br label %18, !dbg !105

18:                                               ; preds = %11
  %19 = load i32, i32* %5, align 4, !dbg !106
  %20 = add nsw i32 %19, 1, !dbg !106
  store i32 %20, i32* %5, align 4, !dbg !106
  br label %7, !dbg !107, !llvm.loop !108

21:                                               ; preds = %7
  %22 = call i32 (i8*, ...) @printf(i8* getelementptr inbounds ([2 x i8], [2 x i8]* @.str.8, i64 0, i64 0)), !dbg !110
  ret void, !dbg !111
}

; Function Attrs: noinline nounwind optnone uwtable
define dso_local i32 @read_num(i32* %0) #0 !dbg !112 {
  %2 = alloca i32, align 4
  %3 = alloca i32*, align 8
  %4 = alloca i32, align 4
  store i32* %0, i32** %3, align 8
  call void @llvm.dbg.declare(metadata i32** %3, metadata !115, metadata !DIExpression()), !dbg !116
  call void @llvm.dbg.declare(metadata i32* %4, metadata !117, metadata !DIExpression()), !dbg !118
  %5 = load i32*, i32** %3, align 8, !dbg !119
  %6 = call i32 (i8*, ...) @__isoc99_scanf(i8* getelementptr inbounds ([3 x i8], [3 x i8]* @.str.3, i64 0, i64 0), i32* %5), !dbg !120
  store i32 %6, i32* %4, align 4, !dbg !118
  %7 = load i32, i32* %4, align 4, !dbg !121
  %8 = icmp ne i32 %7, 1, !dbg !123
  br i1 %8, label %9, label %10, !dbg !124

9:                                                ; preds = %1
  store i32 1, i32* %2, align 4, !dbg !125
  br label %20, !dbg !125

10:                                               ; preds = %1
  %11 = load i32*, i32** %3, align 8, !dbg !127
  %12 = load i32, i32* %11, align 4, !dbg !129
  %13 = icmp slt i32 %12, 1, !dbg !130
  br i1 %13, label %18, label %14, !dbg !131

14:                                               ; preds = %10
  %15 = load i32*, i32** %3, align 8, !dbg !132
  %16 = load i32, i32* %15, align 4, !dbg !133
  %17 = icmp sgt i32 %16, 10, !dbg !134
  br i1 %17, label %18, label %19, !dbg !135

18:                                               ; preds = %14, %10
  store i32 2, i32* %2, align 4, !dbg !136
  br label %20, !dbg !136

19:                                               ; preds = %14
  store i32 0, i32* %2, align 4, !dbg !138
  br label %20, !dbg !138

20:                                               ; preds = %19, %18, %9
  %21 = load i32, i32* %2, align 4, !dbg !139
  ret i32 %21, !dbg !139
}

declare dso_local i32 @__isoc99_scanf(i8*, ...) #3

attributes #0 = { noinline nounwind optnone uwtable "correctly-rounded-divide-sqrt-fp-math"="false" "disable-tail-calls"="false" "frame-pointer"="all" "less-precise-fpmad"="false" "min-legal-vector-width"="0" "no-infs-fp-math"="false" "no-jump-tables"="false" "no-nans-fp-math"="false" "no-signed-zeros-fp-math"="false" "no-trapping-math"="false" "stack-protector-buffer-size"="8" "target-cpu"="x86-64" "target-features"="+cx8,+fxsr,+mmx,+sse,+sse2,+x87" "unsafe-fp-math"="false" "use-soft-float"="false" }
attributes #1 = { nounwind "correctly-rounded-divide-sqrt-fp-math"="false" "disable-tail-calls"="false" "frame-pointer"="all" "less-precise-fpmad"="false" "no-infs-fp-math"="false" "no-nans-fp-math"="false" "no-signed-zeros-fp-math"="false" "no-trapping-math"="false" "stack-protector-buffer-size"="8" "target-cpu"="x86-64" "target-features"="+cx8,+fxsr,+mmx,+sse,+sse2,+x87" "unsafe-fp-math"="false" "use-soft-float"="false" }
attributes #2 = { nounwind readnone speculatable willreturn }
attributes #3 = { "correctly-rounded-divide-sqrt-fp-math"="false" "disable-tail-calls"="false" "frame-pointer"="all" "less-precise-fpmad"="false" "no-infs-fp-math"="false" "no-nans-fp-math"="false" "no-signed-zeros-fp-math"="false" "no-trapping-math"="false" "stack-protector-buffer-size"="8" "target-cpu"="x86-64" "target-features"="+cx8,+fxsr,+mmx,+sse,+sse2,+x87" "unsafe-fp-math"="false" "use-soft-float"="false" }
attributes #4 = { nounwind }

!llvm.dbg.cu = !{!2}
!llvm.ident = !{!11}
!llvm.module.flags = !{!12, !13, !14}

!0 = !DIGlobalVariableExpression(var: !1, expr: !DIExpression())
!1 = distinct !DIGlobalVariable(name: "hidden", scope: !2, file: !3, line: 9, type: !6, isLocal: false, isDefinition: true)
!2 = distinct !DICompileUnit(language: DW_LANG_C99, file: !3, producer: "clang version 10.0.1 ", isOptimized: false, flags: "/opt/mate/llvm-wedlock/bin/clang -g3 -grecord-command-line -emit-llvm -c guessing-game.c -o .guessing-game.c.o.bc", runtimeVersion: 0, emissionKind: FullDebug, enums: !4, globals: !5, splitDebugInlining: false, nameTableKind: None)
!3 = !DIFile(filename: "guessing-game.c", directory: "/tmp/tmp68qqrwba")
!4 = !{}
!5 = !{!0}
!6 = !DIDerivedType(tag: DW_TAG_typedef, name: "secret_t", file: !3, line: 7, baseType: !7)
!7 = distinct !DICompositeType(tag: DW_TAG_structure_type, name: "secret", file: !3, line: 5, size: 32, elements: !8)
!8 = !{!9}
!9 = !DIDerivedType(tag: DW_TAG_member, name: "number", scope: !7, file: !3, line: 6, baseType: !10, size: 32)
!10 = !DIBasicType(name: "int", size: 32, encoding: DW_ATE_signed)
!11 = !{!"clang version 10.0.1 "}
!12 = !{i32 7, !"Dwarf Version", i32 4}
!13 = !{i32 2, !"Debug Info Version", i32 3}
!14 = !{i32 1, !"wchar_size", i32 4}
!15 = distinct !DISubprogram(name: "main", scope: !3, file: !3, line: 14, type: !16, scopeLine: 14, spFlags: DISPFlagDefinition, unit: !2, retainedNodes: !4)
!16 = !DISubroutineType(types: !17)
!17 = !{!10}
!18 = !DILocation(line: 15, column: 19, scope: !15)
!19 = !DILocation(line: 15, column: 26, scope: !15)
!20 = !DILocation(line: 15, column: 31, scope: !15)
!21 = !DILocation(line: 15, column: 17, scope: !15)
!22 = !DILocalVariable(name: "guesses", scope: !15, file: !3, line: 17, type: !23)
!23 = !DIDerivedType(tag: DW_TAG_pointer_type, baseType: !10, size: 64)
!24 = !DILocation(line: 17, column: 8, scope: !15)
!25 = !DILocation(line: 17, column: 18, scope: !15)
!26 = !DILocalVariable(name: "i", scope: !27, file: !3, line: 19, type: !10)
!27 = distinct !DILexicalBlock(scope: !15, file: !3, line: 19, column: 3)
!28 = !DILocation(line: 19, column: 12, scope: !27)
!29 = !DILocation(line: 19, column: 8, scope: !27)
!30 = !DILocation(line: 19, column: 19, scope: !31)
!31 = distinct !DILexicalBlock(scope: !27, file: !3, line: 19, column: 3)
!32 = !DILocation(line: 19, column: 21, scope: !31)
!33 = !DILocation(line: 19, column: 3, scope: !27)
!34 = !DILocation(line: 20, column: 16, scope: !35)
!35 = distinct !DILexicalBlock(scope: !31, file: !3, line: 19, column: 31)
!36 = !DILocation(line: 20, column: 24, scope: !35)
!37 = !DILocation(line: 20, column: 5, scope: !35)
!38 = !DILocation(line: 22, column: 9, scope: !39)
!39 = distinct !DILexicalBlock(scope: !35, file: !3, line: 22, column: 9)
!40 = !DILocation(line: 22, column: 17, scope: !39)
!41 = !DILocation(line: 22, column: 30, scope: !39)
!42 = !DILocation(line: 22, column: 20, scope: !39)
!43 = !DILocation(line: 22, column: 9, scope: !35)
!44 = !DILocation(line: 23, column: 53, scope: !45)
!45 = distinct !DILexicalBlock(scope: !39, file: !3, line: 22, column: 38)
!46 = !DILocation(line: 23, column: 7, scope: !45)
!47 = !DILocation(line: 24, column: 12, scope: !45)
!48 = !DILocation(line: 24, column: 7, scope: !45)
!49 = !DILocation(line: 25, column: 7, scope: !45)
!50 = !DILocation(line: 27, column: 7, scope: !51)
!51 = distinct !DILexicalBlock(scope: !39, file: !3, line: 26, column: 12)
!52 = !DILocation(line: 28, column: 21, scope: !51)
!53 = !DILocation(line: 28, column: 30, scope: !51)
!54 = !DILocation(line: 28, column: 7, scope: !51)
!55 = !DILocation(line: 30, column: 3, scope: !35)
!56 = !DILocation(line: 19, column: 27, scope: !31)
!57 = !DILocation(line: 19, column: 3, scope: !31)
!58 = distinct !{!58, !33, !59}
!59 = !DILocation(line: 30, column: 3, scope: !27)
!60 = !DILocation(line: 32, column: 3, scope: !15)
!61 = !DILocation(line: 34, column: 8, scope: !15)
!62 = !DILocation(line: 34, column: 3, scope: !15)
!63 = !DILocation(line: 35, column: 3, scope: !15)
!64 = !DILocation(line: 36, column: 1, scope: !15)
!65 = distinct !DISubprogram(name: "get_guess", scope: !3, file: !3, line: 49, type: !66, scopeLine: 49, flags: DIFlagPrototyped, spFlags: DISPFlagDefinition, unit: !2, retainedNodes: !4)
!66 = !DISubroutineType(types: !67)
!67 = !{null, !23}
!68 = !DILocalVariable(name: "guess", arg: 1, scope: !65, file: !3, line: 49, type: !23)
!69 = !DILocation(line: 49, column: 21, scope: !65)
!70 = !DILocation(line: 50, column: 3, scope: !65)
!71 = !DILocation(line: 51, column: 3, scope: !65)
!72 = !DILocation(line: 52, column: 18, scope: !73)
!73 = distinct !DILexicalBlock(scope: !74, file: !3, line: 52, column: 9)
!74 = distinct !DILexicalBlock(scope: !65, file: !3, line: 51, column: 16)
!75 = !DILocation(line: 52, column: 9, scope: !73)
!76 = !DILocation(line: 52, column: 25, scope: !73)
!77 = !DILocation(line: 52, column: 9, scope: !74)
!78 = !DILocation(line: 53, column: 7, scope: !79)
!79 = distinct !DILexicalBlock(scope: !73, file: !3, line: 52, column: 31)
!80 = !DILocation(line: 55, column: 7, scope: !81)
!81 = distinct !DILexicalBlock(scope: !73, file: !3, line: 54, column: 12)
!82 = distinct !{!82, !71, !83}
!83 = !DILocation(line: 57, column: 3, scope: !65)
!84 = distinct !DISubprogram(name: "print_guesses", scope: !3, file: !3, line: 60, type: !85, scopeLine: 60, flags: DIFlagPrototyped, spFlags: DISPFlagDefinition, unit: !2, retainedNodes: !4)
!85 = !DISubroutineType(types: !86)
!86 = !{null, !23, !10}
!87 = !DILocalVariable(name: "guesses", arg: 1, scope: !84, file: !3, line: 60, type: !23)
!88 = !DILocation(line: 60, column: 25, scope: !84)
!89 = !DILocalVariable(name: "i", arg: 2, scope: !84, file: !3, line: 60, type: !10)
!90 = !DILocation(line: 60, column: 38, scope: !84)
!91 = !DILocation(line: 61, column: 3, scope: !84)
!92 = !DILocalVariable(name: "j", scope: !93, file: !3, line: 62, type: !10)
!93 = distinct !DILexicalBlock(scope: !84, file: !3, line: 62, column: 3)
!94 = !DILocation(line: 62, column: 12, scope: !93)
!95 = !DILocation(line: 62, column: 8, scope: !93)
!96 = !DILocation(line: 62, column: 19, scope: !97)
!97 = distinct !DILexicalBlock(scope: !93, file: !3, line: 62, column: 3)
!98 = !DILocation(line: 62, column: 24, scope: !97)
!99 = !DILocation(line: 62, column: 21, scope: !97)
!100 = !DILocation(line: 62, column: 3, scope: !93)
!101 = !DILocation(line: 63, column: 19, scope: !102)
!102 = distinct !DILexicalBlock(scope: !97, file: !3, line: 62, column: 32)
!103 = !DILocation(line: 63, column: 27, scope: !102)
!104 = !DILocation(line: 63, column: 5, scope: !102)
!105 = !DILocation(line: 64, column: 3, scope: !102)
!106 = !DILocation(line: 62, column: 28, scope: !97)
!107 = !DILocation(line: 62, column: 3, scope: !97)
!108 = distinct !{!108, !100, !109}
!109 = !DILocation(line: 64, column: 3, scope: !93)
!110 = !DILocation(line: 65, column: 3, scope: !84)
!111 = !DILocation(line: 66, column: 1, scope: !84)
!112 = distinct !DISubprogram(name: "read_num", scope: !3, file: !3, line: 38, type: !113, scopeLine: 38, flags: DIFlagPrototyped, spFlags: DISPFlagDefinition, unit: !2, retainedNodes: !4)
!113 = !DISubroutineType(types: !114)
!114 = !{!10, !23}
!115 = !DILocalVariable(name: "num", arg: 1, scope: !112, file: !3, line: 38, type: !23)
!116 = !DILocation(line: 38, column: 19, scope: !112)
!117 = !DILocalVariable(name: "no", scope: !112, file: !3, line: 39, type: !10)
!118 = !DILocation(line: 39, column: 7, scope: !112)
!119 = !DILocation(line: 39, column: 24, scope: !112)
!120 = !DILocation(line: 39, column: 12, scope: !112)
!121 = !DILocation(line: 40, column: 7, scope: !122)
!122 = distinct !DILexicalBlock(scope: !112, file: !3, line: 40, column: 7)
!123 = !DILocation(line: 40, column: 10, scope: !122)
!124 = !DILocation(line: 40, column: 7, scope: !112)
!125 = !DILocation(line: 41, column: 5, scope: !126)
!126 = distinct !DILexicalBlock(scope: !122, file: !3, line: 40, column: 16)
!127 = !DILocation(line: 43, column: 9, scope: !128)
!128 = distinct !DILexicalBlock(scope: !112, file: !3, line: 43, column: 7)
!129 = !DILocation(line: 43, column: 8, scope: !128)
!130 = !DILocation(line: 43, column: 13, scope: !128)
!131 = !DILocation(line: 43, column: 18, scope: !128)
!132 = !DILocation(line: 43, column: 23, scope: !128)
!133 = !DILocation(line: 43, column: 22, scope: !128)
!134 = !DILocation(line: 43, column: 27, scope: !128)
!135 = !DILocation(line: 43, column: 7, scope: !112)
!136 = !DILocation(line: 44, column: 5, scope: !137)
!137 = distinct !DILexicalBlock(scope: !128, file: !3, line: 43, column: 34)
!138 = !DILocation(line: 46, column: 3, scope: !112)
!139 = !DILocation(line: 47, column: 1, scope: !112)
