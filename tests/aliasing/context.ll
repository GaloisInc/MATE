; ModuleID = 'context.cpp'
source_filename = "context.cpp"
target datalayout = "e-m:e-i64:64-f80:128-n8:16:32:64-S128"
target triple = "x86_64-unknown-linux-gnu"

%class.MyObj = type { i8 }
%class.A1 = type { i8 }
%class.A2 = type { i8 }

; Function Attrs: noinline nounwind optnone sspstrong uwtable
define %class.MyObj* @_Z2idP5MyObj(%class.MyObj*) #0 !dbg !8 {
  %2 = alloca %class.MyObj*, align 8
  store %class.MyObj* %0, %class.MyObj** %2, align 8
  call void @llvm.dbg.declare(metadata %class.MyObj** %2, metadata !13, metadata !DIExpression()), !dbg !14
  %3 = load %class.MyObj*, %class.MyObj** %2, align 8, !dbg !15
  ret %class.MyObj* %3, !dbg !16
}

; Function Attrs: nounwind readnone speculatable
declare void @llvm.dbg.declare(metadata, metadata, metadata) #1

; Function Attrs: noinline optnone sspstrong uwtable
define void @_Z4fun1v() #2 !dbg !17 {
  %1 = alloca %class.MyObj*, align 8
  %2 = alloca %class.MyObj*, align 8
  call void @llvm.dbg.declare(metadata %class.MyObj** %1, metadata !20, metadata !DIExpression()), !dbg !21
  %3 = call i8* @_Znwm(i64 1) #5, !dbg !22
  %4 = bitcast i8* %3 to %class.A1*, !dbg !22
  %5 = bitcast %class.A1* %4 to %class.MyObj*, !dbg !22
  store %class.MyObj* %5, %class.MyObj** %1, align 8, !dbg !21
  call void @llvm.dbg.declare(metadata %class.MyObj** %2, metadata !23, metadata !DIExpression()), !dbg !24
  %6 = load %class.MyObj*, %class.MyObj** %1, align 8, !dbg !25
  %7 = call %class.MyObj* @_Z2idP5MyObj(%class.MyObj* %6), !dbg !26
  store %class.MyObj* %7, %class.MyObj** %2, align 8, !dbg !24
  ret void, !dbg !27
}

; Function Attrs: nobuiltin
declare noalias i8* @_Znwm(i64) #3

; Function Attrs: noinline optnone sspstrong uwtable
define void @_Z4fun2v() #2 !dbg !28 {
  %1 = alloca %class.MyObj*, align 8
  %2 = alloca %class.MyObj*, align 8
  call void @llvm.dbg.declare(metadata %class.MyObj** %1, metadata !29, metadata !DIExpression()), !dbg !30
  %3 = call i8* @_Znwm(i64 1) #5, !dbg !31
  %4 = bitcast i8* %3 to %class.A2*, !dbg !31
  %5 = bitcast %class.A2* %4 to %class.MyObj*, !dbg !31
  store %class.MyObj* %5, %class.MyObj** %1, align 8, !dbg !30
  call void @llvm.dbg.declare(metadata %class.MyObj** %2, metadata !32, metadata !DIExpression()), !dbg !33
  %6 = load %class.MyObj*, %class.MyObj** %1, align 8, !dbg !34
  %7 = call %class.MyObj* @_Z2idP5MyObj(%class.MyObj* %6), !dbg !35
  store %class.MyObj* %7, %class.MyObj** %2, align 8, !dbg !33
  ret void, !dbg !36
}

; Function Attrs: noinline norecurse optnone sspstrong uwtable
define i32 @main() #4 !dbg !37 {
  call void @_Z4fun1v(), !dbg !41
  call void @_Z4fun2v(), !dbg !42
  ret i32 0, !dbg !43
}

attributes #0 = { noinline nounwind optnone sspstrong uwtable "correctly-rounded-divide-sqrt-fp-math"="false" "disable-tail-calls"="false" "less-precise-fpmad"="false" "no-frame-pointer-elim"="true" "no-frame-pointer-elim-non-leaf" "no-infs-fp-math"="false" "no-jump-tables"="false" "no-nans-fp-math"="false" "no-signed-zeros-fp-math"="false" "no-trapping-math"="false" "stack-protector-buffer-size"="4" "target-cpu"="x86-64" "target-features"="+fxsr,+mmx,+sse,+sse2,+x87" "unsafe-fp-math"="false" "use-soft-float"="false" }
attributes #1 = { nounwind readnone speculatable }
attributes #2 = { noinline optnone sspstrong uwtable "correctly-rounded-divide-sqrt-fp-math"="false" "disable-tail-calls"="false" "less-precise-fpmad"="false" "no-frame-pointer-elim"="true" "no-frame-pointer-elim-non-leaf" "no-infs-fp-math"="false" "no-jump-tables"="false" "no-nans-fp-math"="false" "no-signed-zeros-fp-math"="false" "no-trapping-math"="false" "stack-protector-buffer-size"="4" "target-cpu"="x86-64" "target-features"="+fxsr,+mmx,+sse,+sse2,+x87" "unsafe-fp-math"="false" "use-soft-float"="false" }
attributes #3 = { nobuiltin "correctly-rounded-divide-sqrt-fp-math"="false" "disable-tail-calls"="false" "less-precise-fpmad"="false" "no-frame-pointer-elim"="true" "no-frame-pointer-elim-non-leaf" "no-infs-fp-math"="false" "no-nans-fp-math"="false" "no-signed-zeros-fp-math"="false" "no-trapping-math"="false" "stack-protector-buffer-size"="4" "target-cpu"="x86-64" "target-features"="+fxsr,+mmx,+sse,+sse2,+x87" "unsafe-fp-math"="false" "use-soft-float"="false" }
attributes #4 = { noinline norecurse optnone sspstrong uwtable "correctly-rounded-divide-sqrt-fp-math"="false" "disable-tail-calls"="false" "less-precise-fpmad"="false" "no-frame-pointer-elim"="true" "no-frame-pointer-elim-non-leaf" "no-infs-fp-math"="false" "no-jump-tables"="false" "no-nans-fp-math"="false" "no-signed-zeros-fp-math"="false" "no-trapping-math"="false" "stack-protector-buffer-size"="4" "target-cpu"="x86-64" "target-features"="+fxsr,+mmx,+sse,+sse2,+x87" "unsafe-fp-math"="false" "use-soft-float"="false" }
attributes #5 = { builtin }

!llvm.dbg.cu = !{!0}
!llvm.module.flags = !{!3, !4, !5, !6}
!llvm.ident = !{!7}

!0 = distinct !DICompileUnit(language: DW_LANG_C_plus_plus, file: !1, producer: "clang version 7.1.0 (tags/RELEASE_710/final)", isOptimized: false, runtimeVersion: 0, emissionKind: FullDebug, enums: !2)
!1 = !DIFile(filename: "context.cpp", directory: "/home/karl/work/MATE2/tests/aliasing")
!2 = !{}
!3 = !{i32 2, !"Dwarf Version", i32 4}
!4 = !{i32 2, !"Debug Info Version", i32 3}
!5 = !{i32 1, !"wchar_size", i32 4}
!6 = !{i32 7, !"PIC Level", i32 2}
!7 = !{!"clang version 7.1.0 (tags/RELEASE_710/final)"}
!8 = distinct !DISubprogram(name: "id", linkageName: "_Z2idP5MyObj", scope: !1, file: !1, line: 7, type: !9, isLocal: false, isDefinition: true, scopeLine: 7, flags: DIFlagPrototyped, isOptimized: false, unit: !0, retainedNodes: !2)
!9 = !DISubroutineType(types: !10)
!10 = !{!11, !11}
!11 = !DIDerivedType(tag: DW_TAG_pointer_type, baseType: !12, size: 64)
!12 = distinct !DICompositeType(tag: DW_TAG_class_type, name: "MyObj", file: !1, line: 1, size: 8, flags: DIFlagTypePassByValue | DIFlagTrivial, elements: !2, identifier: "_ZTS5MyObj")
!13 = !DILocalVariable(name: "a", arg: 1, scope: !8, file: !1, line: 7, type: !11)
!14 = !DILocation(line: 7, column: 18, scope: !8)
!15 = !DILocation(line: 7, column: 30, scope: !8)
!16 = !DILocation(line: 7, column: 23, scope: !8)
!17 = distinct !DISubprogram(name: "fun1", linkageName: "_Z4fun1v", scope: !1, file: !1, line: 9, type: !18, isLocal: false, isDefinition: true, scopeLine: 9, flags: DIFlagPrototyped, isOptimized: false, unit: !0, retainedNodes: !2)
!18 = !DISubroutineType(types: !19)
!19 = !{null}
!20 = !DILocalVariable(name: "a1", scope: !17, file: !1, line: 10, type: !11)
!21 = !DILocation(line: 10, column: 10, scope: !17)
!22 = !DILocation(line: 10, column: 15, scope: !17)
!23 = !DILocalVariable(name: "b1", scope: !17, file: !1, line: 11, type: !11)
!24 = !DILocation(line: 11, column: 10, scope: !17)
!25 = !DILocation(line: 11, column: 18, scope: !17)
!26 = !DILocation(line: 11, column: 15, scope: !17)
!27 = !DILocation(line: 12, column: 1, scope: !17)
!28 = distinct !DISubprogram(name: "fun2", linkageName: "_Z4fun2v", scope: !1, file: !1, line: 14, type: !18, isLocal: false, isDefinition: true, scopeLine: 14, flags: DIFlagPrototyped, isOptimized: false, unit: !0, retainedNodes: !2)
!29 = !DILocalVariable(name: "a2", scope: !28, file: !1, line: 15, type: !11)
!30 = !DILocation(line: 15, column: 10, scope: !28)
!31 = !DILocation(line: 15, column: 15, scope: !28)
!32 = !DILocalVariable(name: "b2", scope: !28, file: !1, line: 16, type: !11)
!33 = !DILocation(line: 16, column: 10, scope: !28)
!34 = !DILocation(line: 16, column: 18, scope: !28)
!35 = !DILocation(line: 16, column: 15, scope: !28)
!36 = !DILocation(line: 17, column: 1, scope: !28)
!37 = distinct !DISubprogram(name: "main", scope: !1, file: !1, line: 19, type: !38, isLocal: false, isDefinition: true, scopeLine: 19, flags: DIFlagPrototyped, isOptimized: false, unit: !0, retainedNodes: !2)
!38 = !DISubroutineType(types: !39)
!39 = !{!40}
!40 = !DIBasicType(name: "int", size: 32, encoding: DW_ATE_signed)
!41 = !DILocation(line: 20, column: 3, scope: !37)
!42 = !DILocation(line: 21, column: 3, scope: !37)
!43 = !DILocation(line: 22, column: 1, scope: !37)
