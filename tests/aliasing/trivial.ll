; ModuleID = 'trivial.c'
source_filename = "trivial.c"
target datalayout = "e-m:e-i64:64-f80:128-n8:16:32:64-S128"
target triple = "x86_64-unknown-linux-gnu"

@.str = private unnamed_addr constant [6 x i8] c"%d %d\00", align 1

; Function Attrs: noinline nounwind optnone sspstrong uwtable
define i32 @foo() #0 !dbg !8 {
  ret i32 2, !dbg !12
}

; Function Attrs: noinline nounwind optnone sspstrong uwtable
define i32 @main() #0 !dbg !13 {
  %1 = alloca i32, align 4
  %2 = alloca i32, align 4
  %3 = alloca i32, align 4
  %4 = alloca i32, align 4
  %5 = alloca i32, align 4
  %6 = alloca i32, align 4
  %7 = alloca [4 x i32*], align 16
  %8 = alloca i32*, align 8
  %9 = alloca i32*, align 8
  call void @llvm.dbg.declare(metadata i32* %1, metadata !14, metadata !DIExpression()), !dbg !15
  %10 = call i32 @foo(), !dbg !16
  store i32 %10, i32* %1, align 4, !dbg !15
  call void @llvm.dbg.declare(metadata i32* %2, metadata !17, metadata !DIExpression()), !dbg !18
  %11 = call i32 @foo(), !dbg !19
  store i32 %11, i32* %2, align 4, !dbg !18
  call void @llvm.dbg.declare(metadata i32* %3, metadata !20, metadata !DIExpression()), !dbg !21
  store i32 0, i32* %3, align 4, !dbg !21
  call void @llvm.dbg.declare(metadata i32* %4, metadata !22, metadata !DIExpression()), !dbg !23
  store i32 1, i32* %4, align 4, !dbg !23
  call void @llvm.dbg.declare(metadata i32* %5, metadata !24, metadata !DIExpression()), !dbg !25
  store i32 2, i32* %5, align 4, !dbg !25
  call void @llvm.dbg.declare(metadata i32* %6, metadata !26, metadata !DIExpression()), !dbg !27
  store i32 3, i32* %6, align 4, !dbg !27
  call void @llvm.dbg.declare(metadata [4 x i32*]* %7, metadata !28, metadata !DIExpression()), !dbg !33
  %12 = getelementptr inbounds [4 x i32*], [4 x i32*]* %7, i64 0, i64 0, !dbg !34
  store i32* %3, i32** %12, align 8, !dbg !34
  %13 = getelementptr inbounds i32*, i32** %12, i64 1, !dbg !34
  store i32* %4, i32** %13, align 8, !dbg !34
  %14 = getelementptr inbounds i32*, i32** %13, i64 1, !dbg !34
  store i32* %5, i32** %14, align 8, !dbg !34
  %15 = getelementptr inbounds i32*, i32** %14, i64 1, !dbg !34
  store i32* %6, i32** %15, align 8, !dbg !34
  call void @llvm.dbg.declare(metadata i32** %8, metadata !35, metadata !DIExpression()), !dbg !36
  %16 = load i32, i32* %1, align 4, !dbg !37
  %17 = sext i32 %16 to i64, !dbg !38
  %18 = getelementptr [4 x i32*], [4 x i32*]* %7, i64 0, i64 %17, !dbg !38
  %19 = load i32*, i32** %18, align 8, !dbg !38
  store i32* %19, i32** %8, align 8, !dbg !36
  call void @llvm.dbg.declare(metadata i32** %9, metadata !39, metadata !DIExpression()), !dbg !40
  %20 = load i32, i32* %2, align 4, !dbg !41
  %21 = sext i32 %20 to i64, !dbg !42
  %22 = getelementptr [4 x i32*], [4 x i32*]* %7, i64 0, i64 %21, !dbg !42
  %23 = load i32*, i32** %22, align 8, !dbg !42
  store i32* %23, i32** %9, align 8, !dbg !40
  %24 = load i32*, i32** %8, align 8, !dbg !43
  %25 = load i32, i32* %24, align 4, !dbg !44
  %26 = load i32*, i32** %9, align 8, !dbg !45
  %27 = load i32, i32* %26, align 4, !dbg !46
  %28 = call i32 (i8*, ...) @printf(i8* getelementptr inbounds ([6 x i8], [6 x i8]* @.str, i32 0, i32 0), i32 %25, i32 %27), !dbg !47
  ret i32 0, !dbg !48
}

; Function Attrs: nounwind readnone speculatable
declare void @llvm.dbg.declare(metadata, metadata, metadata) #1

declare i32 @printf(i8*, ...) #2

attributes #0 = { noinline nounwind optnone sspstrong uwtable "correctly-rounded-divide-sqrt-fp-math"="false" "disable-tail-calls"="false" "less-precise-fpmad"="false" "no-frame-pointer-elim"="true" "no-frame-pointer-elim-non-leaf" "no-infs-fp-math"="false" "no-jump-tables"="false" "no-nans-fp-math"="false" "no-signed-zeros-fp-math"="false" "no-trapping-math"="false" "stack-protector-buffer-size"="4" "target-cpu"="x86-64" "target-features"="+fxsr,+mmx,+sse,+sse2,+x87" "unsafe-fp-math"="false" "use-soft-float"="false" }
attributes #1 = { nounwind readnone speculatable }
attributes #2 = { "correctly-rounded-divide-sqrt-fp-math"="false" "disable-tail-calls"="false" "less-precise-fpmad"="false" "no-frame-pointer-elim"="true" "no-frame-pointer-elim-non-leaf" "no-infs-fp-math"="false" "no-nans-fp-math"="false" "no-signed-zeros-fp-math"="false" "no-trapping-math"="false" "stack-protector-buffer-size"="4" "target-cpu"="x86-64" "target-features"="+fxsr,+mmx,+sse,+sse2,+x87" "unsafe-fp-math"="false" "use-soft-float"="false" }

!llvm.dbg.cu = !{!0}
!llvm.module.flags = !{!3, !4, !5, !6}
!llvm.ident = !{!7}

!0 = distinct !DICompileUnit(language: DW_LANG_C99, file: !1, producer: "clang version 7.0.1 (tags/RELEASE_701/final)", isOptimized: false, runtimeVersion: 0, emissionKind: FullDebug, enums: !2)
!1 = !DIFile(filename: "trivial.c", directory: "/home/karl/work/MATE2/tests/aliasing")
!2 = !{}
!3 = !{i32 2, !"Dwarf Version", i32 4}
!4 = !{i32 2, !"Debug Info Version", i32 3}
!5 = !{i32 1, !"wchar_size", i32 4}
!6 = !{i32 7, !"PIC Level", i32 2}
!7 = !{!"clang version 7.0.1 (tags/RELEASE_701/final)"}
!8 = distinct !DISubprogram(name: "foo", scope: !1, file: !1, line: 3, type: !9, isLocal: false, isDefinition: true, scopeLine: 3, isOptimized: false, unit: !0, retainedNodes: !2)
!9 = !DISubroutineType(types: !10)
!10 = !{!11}
!11 = !DIBasicType(name: "int", size: 32, encoding: DW_ATE_signed)
!12 = !DILocation(line: 3, column: 13, scope: !8)
!13 = distinct !DISubprogram(name: "main", scope: !1, file: !1, line: 5, type: !9, isLocal: false, isDefinition: true, scopeLine: 5, isOptimized: false, unit: !0, retainedNodes: !2)
!14 = !DILocalVariable(name: "x", scope: !13, file: !1, line: 6, type: !11)
!15 = !DILocation(line: 6, column: 7, scope: !13)
!16 = !DILocation(line: 6, column: 11, scope: !13)
!17 = !DILocalVariable(name: "y", scope: !13, file: !1, line: 7, type: !11)
!18 = !DILocation(line: 7, column: 7, scope: !13)
!19 = !DILocation(line: 7, column: 11, scope: !13)
!20 = !DILocalVariable(name: "a", scope: !13, file: !1, line: 9, type: !11)
!21 = !DILocation(line: 9, column: 7, scope: !13)
!22 = !DILocalVariable(name: "b", scope: !13, file: !1, line: 10, type: !11)
!23 = !DILocation(line: 10, column: 7, scope: !13)
!24 = !DILocalVariable(name: "c", scope: !13, file: !1, line: 11, type: !11)
!25 = !DILocation(line: 11, column: 7, scope: !13)
!26 = !DILocalVariable(name: "d", scope: !13, file: !1, line: 12, type: !11)
!27 = !DILocation(line: 12, column: 7, scope: !13)
!28 = !DILocalVariable(name: "arr", scope: !13, file: !1, line: 13, type: !29)
!29 = !DICompositeType(tag: DW_TAG_array_type, baseType: !30, size: 256, elements: !31)
!30 = !DIDerivedType(tag: DW_TAG_pointer_type, baseType: !11, size: 64)
!31 = !{!32}
!32 = !DISubrange(count: 4)
!33 = !DILocation(line: 13, column: 8, scope: !13)
!34 = !DILocation(line: 13, column: 16, scope: !13)
!35 = !DILocalVariable(name: "px", scope: !13, file: !1, line: 15, type: !30)
!36 = !DILocation(line: 15, column: 8, scope: !13)
!37 = !DILocation(line: 15, column: 17, scope: !13)
!38 = !DILocation(line: 15, column: 13, scope: !13)
!39 = !DILocalVariable(name: "py", scope: !13, file: !1, line: 16, type: !30)
!40 = !DILocation(line: 16, column: 8, scope: !13)
!41 = !DILocation(line: 16, column: 17, scope: !13)
!42 = !DILocation(line: 16, column: 13, scope: !13)
!43 = !DILocation(line: 18, column: 20, scope: !13)
!44 = !DILocation(line: 18, column: 19, scope: !13)
!45 = !DILocation(line: 18, column: 25, scope: !13)
!46 = !DILocation(line: 18, column: 24, scope: !13)
!47 = !DILocation(line: 18, column: 3, scope: !13)
!48 = !DILocation(line: 19, column: 1, scope: !13)
