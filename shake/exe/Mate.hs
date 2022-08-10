{-# LANGUAGE LambdaCase #-}

import Control.Monad
import qualified Data.List as L
import Data.Maybe (fromMaybe)

import Development.Shake
import qualified Development.Shake.BuildConfig as BuildConfig
import Development.Shake.Changes
import Development.Shake.FilePath
import Development.Shake.Hybrid
import Development.Shake.Lint

import System.Console.GetOpt (OptDescr)
import System.Directory hiding (doesFileExist)
import System.Environment (lookupEnv)
import System.Exit (ExitCode(ExitSuccess))
import System.Process (readProcessWithExitCode)

runShake :: ShakeOptions
         -> [OptDescr (Either String (a -> a))]
         -> a
         -> (a -> [String] -> IO (Maybe (Rules())))
         -> IO ()
runShake options extraFlags defaults ruleSet =
  shakeArgsWith options extraFlags $ \flags targets ->
    ruleSet (foldl (flip ($)) defaults flags) targets

main :: IO ()
main =
  let sOpts = shakeOptions { shakeCommandOptions = [AddEnv "LC_ALL" "C"] }
  in runShake sOpts BuildConfig.buildFlags BuildConfig.defaultBuildConfig $
       \buildConfig rawArgs -> return $ Just $ do

  getSanitizers <- BuildConfig.setupSanitizerOracle buildConfig
  doReleaseBuild <- BuildConfig.setupReleaseBuildOracle buildConfig
  doScanBuild <- BuildConfig.setupScanBuildOracle buildConfig
  opaque <- BuildConfig.setupOpaqueOracle

  sourceRoot <- liftIO getCurrentDirectory

  let bDistRoot = BuildConfig.out buildConfig </> "bdist"
      buildRoot = BuildConfig.out buildConfig </> "build"
      cacheRoot = BuildConfig.out buildConfig </> "cache"

      localDocRoot = bDistRoot </> "local/doc"

      pythonGlobalRoot = bDistRoot </> "lib/python3.8/site-packages"
      pythonLocalRoot = bDistRoot </> "local/lib/python3.8/site-packages"

  bDistAbs <- liftIO $ makeAbsolute bDistRoot
  pyDistAbs <- liftIO $ makeAbsolute (buildRoot </> "pydist")
  pythonPath <- fromMaybe "" <$> liftIO (lookupEnv "PYTHONPATH")
  ldLibraryPath <- fromMaybe "" <$> liftIO (lookupEnv "LD_LIBRARY_PATH")
  pathPath <- fromMaybe "" <$> liftIO (lookupEnv "PATH")

  -- When running on MRs, use git to see which files we need to lint, format,
  -- etc. When running on MRs into stable, always lint/format everything.
  (code, _, _) <- liftIO $ readProcessWithExitCode "bash" ["ci/on-stable.sh"] ""
  needHasChangedFunc <-
    if code == ExitSuccess
    then pure needHasChanged
    else liftIO getNeedHasChangedFunc

  let addToEnvironmentVariable var newPath originalValue =
        AddEnv var (newPath ++ ":" ++ originalValue)
  let addBDistToPythonPath =
        addToEnvironmentVariable
          "PYTHONPATH"
          (bDistAbs </> "local/lib/python3.8/site-packages" ++ ":" ++
           bDistAbs </> "lib/python3.8/site-packages")
          pythonPath
  let addBDistToLdLibraryPath =
        addToEnvironmentVariable
          "LD_LIBRARY_PATH"
          (bDistAbs </> "local/lib" ++ ":" ++ bDistAbs </> "lib")
          ldLibraryPath
  let addBDistBinsToPath =
        addToEnvironmentVariable
          "PATH"
          (bDistAbs </> "local/bin" ++ ":" ++ bDistAbs </> "bin")
          pathPath

  let localExecutable sourcePath = do
        (bDistRoot </> "local/bin" </> takeFileName sourcePath) %> \targetPath ->
          copyFile' sourcePath targetPath
        return $ return [bDistRoot </> "local/bin" </> takeFileName sourcePath]

  pipCache <- liftIO . makeAbsolute $ cacheRoot </> "pip"
  let pipInstallBase :: [CmdOption] -> [String] -> Action ()
      pipInstallBase opts what =
        cmd_
          opts
          ([ "python3"
           , "-m" , "pip"
           , "install"
           , "--upgrade"
           , "-I"
           , "--cache-dir", pipCache
           , "--no-warn-script-location"
           ] ++ what)
  let pipInstallPrefix opts what =
        pipInstallBase opts (["--prefix", bDistAbs] ++ what)

  let buildPythonDistributions :: String -> Action ()
      buildPythonDistributions tgt = do
        cmd_ [ "python3"
             , "-m"
             , "build"
             , "--sdist"
             , "--wheel"
             , "--outdir"
             , pyDistAbs
             , tgt ]
        -- Extremely annoying: Python's `build`/`wheel` don't provide any way to control
        -- or disable this intermediate build directory. If we don't remove it, it causes
        -- all kinds of problems for every other tool that expects unique module trees
        -- since it contains a copy of each built Python module. Instead of N*M configured
        -- exceptions for N packages and M linting/packaging tools, we clear it as soon
        -- as we're done.
        cmd_ [ "rm", "-rf", tgt </> "build" ]

  let benchmarkCache = cacheRoot </> "benchmarks"
  let callPytest doBenchmark args = do
        need ["build"]
        llvmFlags <- opaque "llvm"
        cmd_
          ([ addBDistToPythonPath
           , addBDistToLdLibraryPath
           -- Needed for Manticore to run and find z3
           , addBDistBinsToPath
           -- Needed for Dwarfcore Makefile
           , AddEnv "MATE" (bDistAbs </> "local/bin/mate")
           , AddEnv "MATE_BDIST_ROOT" bDistAbs
           -- Necessary for doctest on installed modules:
           -- https://github.com/pytest-dev/pytest/issues/2042
           , AddEnv "PY_IGNORE_IMPORTMISMATCH" "1"
           -- Runtime checks for e.g. unclosed file handles
           , AddEnv "PYTHONDEVMODE" "1"
           , AddEnv "PYTHONWARNINGS" $
               L.intercalate "," [ "ignore"
                                 , "error:::dwarfcore[.*]"
                                 , "error:::dwarflang[.*]"
                                 , "error:::mantiserve[.*]"
                                 , "error:::mate[.*]"
                                 ]
           ] ++ llvmFlags)
          ([ "pytest"
           , "-vv"
           , "--show-capture=all"
           , "--rootdir=."
           , "--benchmark-storage=" ++ benchmarkCache
           , if doBenchmark
             then "--benchmark-only"
             else "--benchmark-skip"
           ] ++ args)

  let cmakeConfigure dir = do
        liftIO $ createDirectoryIfMissing True (buildRoot </> "llvm")
        opqFlags <- concat <$> mapM opaque ["llvm"]
        releaseBuild <- doReleaseBuild
        sanitizers <- getSanitizers
        cmd_
          [Cwd dir]
          opqFlags
          ([ "cmake"
          , "-G"
          , "Ninja"
          , "-DCMAKE_EXPORT_COMPILE_COMMANDS=1"
          , if releaseBuild
            then "-DCMAKE_BUILD_TYPE=MATERelease"
            else "-DCMAKE_BUILD_TYPE=MATEDebug"
          , (sourceRoot </> "llvm")
          ] ++ BuildConfig.sanitizerCMakeFlags sanitizers)

  let cmakeBuild dir target = do
        need =<< getCMakeFiles
        opqFlags <- concat <$> mapM opaque ["llvm"]
        cmakeConfigure dir
        numProcs <- shakeThreads <$> getShakeOptions
        scanBuild <- doScanBuild
        cmd_ [Cwd dir] opqFlags $ concat $
          [ if scanBuild
            then [ "scan-build-10"
                  , "-o"
                  , "reports"
                  , "--status-bugs"
                  , "--keep-cc"
                  ]
            else []
          , ["cmake", "--build", "."]
          , maybe [] (\tgt -> ["--target", tgt]) target
          , ["--", "-j" ++ show numProcs]
          ]

  let (targets, arguments) = parseRawArguments rawArgs

  if null targets
    then do
      action $ putNormal "! No targets specified, building everything..."
      want ["build"]
    else want targets

  "clean" ~> do
    removeFilesAfter (buildRoot </> "llvm") ["//*"]
    forP_ ["dwarflang", "dwarfcore", "frontend", "manticore", "mantiserve"] $ \d -> do
      removeFilesAfter (d </> "dist") ["//*"]
      removeFilesAfter (d </> "build") ["//*"]

  let mateSOs = [ "headache/LLVMHeadache.so"
                , "nomina/LLVMNomina.so"
                , "MATE/libMATE.so"
                , "PointerAnalysis/libPAPass.so"
                , "PointerAnalysis/libSoufflePA.so"
                ]

  (bDistRoot </> "local/lib" <*/> map takeFileName mateSOs) &%> \_ ->
    forM_ mateSOs $ \mateSO ->
      copyFile' (buildRoot </> "llvm" </> mateSO)
                (bDistRoot </> "local/lib" </> takeFileName mateSO)

  let smtlibFiles = [ "SMTLIBv2Lexer.interp"
                    , "SMTLIBv2Lexer.tokens"
                    , "SMTLIBv2Lexer.py"
                    , "SMTLIBv2Listener.py"
                    , "SMTLIBv2Parser.py"
                    , "SMTLIBv2.interp"
                    , "SMTLIBv2.tokens"
                    ]

  (buildRoot </> "smt2lib" <*/> smtlibFiles) &%> \_ -> do
    need ("pysmt2lib/smt2lib" <*/> ["SMTLIBv2.g4"])
    cmd_ [Cwd "pysmt2lib/smt2lib"]
         "antlr4" "-Dlanguage=Python3" "-o" (sourceRoot </> buildRoot </> "smt2lib")
         "SMTLIBv2.g4"

  dwarflangPackage <- group
    [ localPythonPackage "dwarflang/dwarflang" (pythonLocalRoot </> "dwarflang")
    ]

  -- The mate-common package
  mateCommonPackage <- group $
    [ localPythonPackage "frontend/mate-common/mate_common" (pythonLocalRoot </> "mate_common")
    -- TODO: Abstract this out into a 'copyPattern' rule.
    , copyRule "frontend/mate-common/mate_common/schemata/nodes.json"
               (pythonLocalRoot </> "mate_common/schemata/nodes.json")
    , copyRule "frontend/mate-common/mate_common/schemata/edges.json"
               (pythonLocalRoot </> "mate_common/schemata/edges.json")
    , copyRule "frontend/mate-common/mate_common/schemata/endpoints.json"
               (pythonLocalRoot </> "mate_common/schemata/endpoints.json")
    , copyRule "frontend/mate-common/mate_common/schemata/relationships.json"
               (pythonLocalRoot </> "mate_common/schemata/relationships.json")
    , copyRule "frontend/mate-common/mate_common/schemata/signatures.json"
               (pythonLocalRoot </> "mate_common/schemata/signatures.json")
    , do (pythonGlobalRoot </> "mate_common_requirements.txt") %> \_ -> do
           need [ "frontend/mate-common/requirements.txt" ]
           pipInstallPrefix [] [ "--upgrade", "-r", "frontend/mate-common/requirements.txt" ]
           copyFile' "frontend/mate-common/requirements.txt" ( pythonGlobalRoot </> "mate_common_requirements.txt" )
         return $ return [pythonGlobalRoot </> "mate_common_requirements.txt"]
    ]

  -- The mate-rest-client package
  mateRestClientPackage <- group $
    [ localPythonPackage "frontend/mate-rest-client/mate_rest_client" (pythonLocalRoot </> "mate_rest_client")
    , do (pythonGlobalRoot </> "mate_rest_client_requirements.txt") %> \_ -> do
           need [ "frontend/mate-rest-client/requirements.txt" ]
           pipInstallPrefix [] [ "--upgrade", "-r", "frontend/mate-rest-client/requirements.txt" ]
           copyFile' "frontend/mate-rest-client/requirements.txt" ( pythonGlobalRoot </> "mate_rest_client_requirements.txt" )
         return $ return [pythonGlobalRoot </> "mate_rest_client_requirements.txt"]
    ]

  -- The mate-cli package
  mateCliPackage <- group $
    [ localPythonPackage "frontend/mate-cli/mate_cli" (pythonLocalRoot </> "mate_cli")
    , do (pythonGlobalRoot </> "mate_cli_requirements.txt") %> \_ -> do
           need [ "frontend/mate-cli/requirements.txt" ]
           pipInstallPrefix [] [ "--upgrade", "-r", "frontend/mate-cli/requirements.txt" ]
           copyFile' "frontend/mate-cli/requirements.txt" ( pythonGlobalRoot </> "mate_cli_requirements.txt" )
         return $ return [pythonGlobalRoot </> "mate_cli_requirements.txt"]
    ]

  -- The mate-query package
  mateQueryPackage <- group $
    [ localPythonPackage "frontend/mate-query/mate_query" (pythonLocalRoot </> "mate_query")
    , do (pythonGlobalRoot </> "mate_query_requirements.txt") %> \_ -> do
           need [ "frontend/mate-query/requirements.txt" ]
           pipInstallPrefix [] [ "--upgrade", "-r", "frontend/mate-query/requirements.txt" ]
           copyFile' "frontend/mate-query/requirements.txt" ( pythonGlobalRoot </> "mate_query_requirements.txt" )
         return $ return [pythonGlobalRoot </> "mate_query_requirements.txt"]
    ]

  -- The mate package
  matePackage <- group $
    [ localPythonPackage "frontend/mate/mate" (pythonLocalRoot </> "mate")
    , localExecutable "frontend/mate/bin/mate"
    , localExecutable "frontend/mate/bin/mate-bridge"
    , localExecutable "frontend/mate/bin/mate-cli"
    , localExecutable "frontend/mate/bin/mate-docs"
    , do (pythonGlobalRoot </> "mate_requirements.txt") %> \_ -> do
           need ["frontend/mate/requirements.txt"]
           pipInstallPrefix
            [ AddEnv "LLVM_DIR" (bDistAbs </> "llvm-wedlock/lib/cmake/llvm")
            , AddEnv "Clang_DIR" (bDistAbs </> "llvm-wedlock/lib/cmake/clang") ]
            ["--upgrade", "-r", "frontend/mate/requirements.txt"]
           copyFile' "frontend/mate/requirements.txt" (pythonGlobalRoot </> "mate_requirements.txt")
         return $ return [pythonGlobalRoot </> "mate_requirements.txt"]
    ]

  mantiservePackage <- group $
    [ localPythonPackage "mantiserve/mantiserve" (pythonLocalRoot </> "mantiserve")
    , do (pythonGlobalRoot </> "mantiserve_requirements.txt") %> \_ -> do
           need ["mantiserve/requirements.txt"]
           pipInstallPrefix [] ["--upgrade", "-r", "mantiserve/requirements.txt"]
           copyFile' "mantiserve/requirements.txt" (pythonGlobalRoot </> "mantiserve_requirements.txt")
         return $ return [pythonGlobalRoot </> "mantiserve_requirements.txt"]
    ]

  dwarfcorePackage <- group $
    [ localPythonPackage "dwarfcore/dwarfcore" (pythonLocalRoot </> "dwarfcore")
    ]

  manticorePackage <- group $
    [ localPythonPackage "submodules/manticore/manticore" (pythonLocalRoot </> "manticore")
    ]

  pysmt2libPackage <- group $
    [ localPythonPackage
        "pysmt2lib/smt2lib"
        (pythonLocalRoot </> "smt2lib")
    ] ++ (flip map smtlibFiles $ \f ->
       copyRule (buildRoot </> "smt2lib" </> f)
                (pythonLocalRoot </> "smt2lib" </> f))

  "pydists" ~> do
    -- TODO: Add others to this list.
    need =<< concat <$> sequence [ mateCommonPackage
                                 , mateRestClientPackage
                                 , mateCliPackage
                                 , mateQueryPackage
                                 ]

    buildPythonDistributions "frontend/mate-common"
    buildPythonDistributions "frontend/mate-rest-client"
    buildPythonDistributions "frontend/mate-cli"
    buildPythonDistributions "frontend/mate-query"

  "bdist-py" ~> do
    need =<< concat <$> sequence [ mateCommonPackage
                                 , mateRestClientPackage
                                 , mateCliPackage
                                 , mateQueryPackage
                                 , matePackage
                                 , pysmt2libPackage
                                 , dwarflangPackage
                                 , dwarfcorePackage
                                 , mantiservePackage
                                 , manticorePackage
                                 ]

    liftIO $ createDirectoryIfMissing True pipCache

  "bdist-go" ~> do
    need [ bDistRoot </> "libexec/gclang" ]

  (bDistRoot </> "libexec/gclang") %> \_ ->
    cmd_ [
           AddEnv "GO111MODULE" "on"
         , AddEnv "GOBIN" (bDistAbs </> "libexec")
         ]
         "go" ["get", "github.com/SRI-CSL/gllvm/cmd/...@938e851"]

  "doc" ~> do
    need [ "bdist-py"
         , localDocRoot </> "html/api.html"
         , localDocRoot </> "html/index.html"
         ]

  (bDistRoot </> "local/share/default-signatures.yml") %> \_ ->
    copyFile' (sourceRoot </> "default-signatures.yml")
              (bDistRoot </> "local/share/default-signatures.yml")

  "bdist" ~> do
    need [ "build", "doc" ]

  let schemaDotFile = buildRoot </> "doc" </> "schema.dot"

  schemaDotFile %> \_ -> do
    let schemaDir = "frontend/mate-common/mate_common/schemata"
        nodeSchema = schemaDir </> "nodes.json"
        edgeSchema = schemaDir </> "edges.json"
        endpointsSchema = schemaDir </> "endpoints.json"
        relationshipsSchema = schemaDir </> "relationships.json"
        script = "doc/schemata/diagram.py"
    need [ script
         , nodeSchema
         , edgeSchema
         , endpointsSchema
         , relationshipsSchema
         , "bdist-py"
         ]
    liftIO $ createDirectoryIfMissing True (buildRoot </> "doc")
    cmd_ [ addBDistToPythonPath ]
         [ "python3"
         , script
         , "--node-schema=" ++ nodeSchema
         , "--edge-schema=" ++ edgeSchema
         , "--endpoints-schema=" ++ endpointsSchema
         , "--relationships-schema=" ++ relationshipsSchema
         , "--output=" ++ schemaDotFile
         ]

  let schemaDiagramDir = localDocRoot </> "html/schemata"
      schemaDiagram = schemaDiagramDir </> "schema.png"

  schemaDiagram %> \_ -> do
    need [schemaDotFile]
    liftIO $ createDirectoryIfMissing True (buildRoot </> "doc")
    dotFiles <- getDirectoryFiles sourceRoot [buildRoot </> "doc" ++ "//*.dot"]
    need dotFiles
    forM_ dotFiles $ \dotFile -> do
      let dest = schemaDiagramDir </> dropExtension (takeFileName dotFile) ++ ".png"
      cmd_ ["dot", "-Tpng", "-o", dest, dotFile]

  let mustacheJSON = cpgSchemaDocDir </> "mustache.json"
      cpgSchemaDocDir = buildRoot </> "doc/schemata"
      cpgRstTemplate = "doc/schemata/cpg.rst.mustache"
  (buildRoot </> cpgRstTemplate) %> \_ ->
    copyFile' cpgRstTemplate (buildRoot </> cpgRstTemplate)
  mustacheJSON %> \_ -> do
    liftIO $ createDirectoryIfMissing True cpgSchemaDocDir
    copyFile' "frontend/mate-common/mate_common/schemata/nodes.json" (cpgSchemaDocDir </> "nodes.json")
    copyFile' "frontend/mate-common/mate_common/schemata/edges.json" (cpgSchemaDocDir </> "edges.json")
    files <- getDirectoryFiles "" ["doc/schemata//*"]
    forP_ files $
      \file -> copyFile' file (cpgSchemaDocDir </> takeFileName file)
    cmd_ [Cwd cpgSchemaDocDir] "python3 mustache.py"

  let cpgSchemaDoc = cpgSchemaDocDir </> "cpg.rst"
  cpgSchemaDoc %> \_ -> do
    need [buildRoot </> cpgRstTemplate, mustacheJSON]
    liftIO $ createDirectoryIfMissing True cpgSchemaDocDir
    cmd_
      [ FileStdin mustacheJSON
      , FileStdout cpgSchemaDoc
      ]
      "mustache"
      "doc/schemata/cpg.rst.mustache"

  let apidocTargetPath = buildRoot </> "doc/api"
      apidocLocalPythonPackage :: Action [FilePath] -> String -> FilePath -> HybridRule
      apidocLocalPythonPackage package name sourcePath =
        let targetPath = apidocTargetPath </> name
        in do
          (targetPath <//> "*.rst") %> \_ -> do
            need =<< package
            cmd_
              "sphinx-apidoc"
              [Cwd apidocTargetPath, addBDistToPythonPath, addBDistBinsToPath]
              ["-f", "-Me", "-H", name ++ " API Reference", "-d", "0", "-o", name, sourceRoot </> sourcePath]
          return $ do
            return [targetPath </> "modules.rst"]

  apidocMateCommon <-
    group [ apidocLocalPythonPackage mateCommonPackage "MATECommon" "frontend/mate-common/mate_common" ]
  apidocMateRestClient <-
    group [ apidocLocalPythonPackage mateRestClientPackage "MATERestClient" "frontend/mate-rest-client/mate_rest_client" ]
  apidocMateCli <-
    group [ apidocLocalPythonPackage mateCliPackage "MATECli" "frontend/mate-cli/mate_cli" ]
  apidocMateQuery <-
    group [ apidocLocalPythonPackage mateQueryPackage "MATEQuery" "frontend/mate-query/mate_query" ]
  apidocMate <-
    group [ apidocLocalPythonPackage matePackage "MATE" "frontend/mate/mate" ]
  apidocMantiserve <-
    group [ apidocLocalPythonPackage mantiservePackage "Mantiserve" "mantiserve/mantiserve" ]
  apidocDwarfcore <-
    group [ apidocLocalPythonPackage dwarfcorePackage "Dwarfcore" "dwarfcore/dwarfcore" ]
  apidocDwarflang <-
    group [ apidocLocalPythonPackage dwarflangPackage "Dwarflang" "dwarflang/dwarflang" ]

  (localDocRoot </> "html/index.html") %> \_ -> do
    rstFiles <- getDirectoryFiles sourceRoot ["doc/*.rst"]
    pyFiles <- getDirectoryFiles sourceRoot ["doc//*.py"]
    assetFiles <- getDirectoryFiles sourceRoot ["doc/assets/*"]
    mateCommonPackageFiles <- mateCommonPackage
    mateRestClientPackageFiles <- mateRestClientPackage
    mateCliPackageFiles <- mateCliPackage
    mateQueryPackageFiles <- mateQueryPackage
    matePackageFiles <- matePackage
    apidocFiles <-
      concat <$> sequence [ apidocMateCommon
                          , apidocMateRestClient
                          , apidocMateCli
                          , apidocMateQuery
                          , apidocMate
                          , apidocMantiserve
                          , apidocDwarfcore
                          , apidocDwarflang ]
    need $ concat $
        [ [cpgSchemaDoc, schemaDiagram]
        , rstFiles
        , pyFiles
        , assetFiles
        , mateCommonPackageFiles
        , mateRestClientPackageFiles
        , mateCliPackageFiles
        , mateQueryPackageFiles
        , matePackageFiles
        , apidocFiles
        ]
    liftIO $ createDirectoryIfMissing True (buildRoot </> "doc/api")
    copyFile' "doc/api/index.rst" (buildRoot </> "doc/api/index.rst")
    copyFile' "llvm/PointerAnalysis/README.rst" (buildRoot </> "doc/standalonepa.rst")
    forP_ (rstFiles ++ pyFiles) $
      \file -> copyFile' file (buildRoot </> "doc" </> takeFileName file)
    forP_ assetFiles $
      \file -> copyFile' file (buildRoot </> "doc/assets" </> takeFileName file)
    numProcs <- shakeThreads <$> getShakeOptions
    let sphinxBuild = cmd_
                        [Cwd (buildRoot </> "doc"), addBDistToPythonPath, addBDistBinsToPath]
                        "sphinx-build"
                        [".", "-j", show numProcs]
    sphinxBuild ["-b", "html", sourceRoot </> bDistRoot </> "local/doc/html"]
    -- NOTE: Re-enable this if you need the LaTeX build.
    -- sphinxBuild ["-b", "latex", sourceRoot </> bDistRoot </> "local/doc/latex"]

  (localDocRoot </> "html/api.html") %> \_ -> do
    need . concat =<< sequence [ mateCommonPackage
                               , mantiservePackage
                               , apidocMateRestClient
                               , apidocMateCli
                               , apidocMateQuery
                               , apidocMate
                               , matePackage
                               , dwarflangPackage ]
    cmd_
      [Cwd (localDocRoot </> "html"), addBDistToPythonPath, addBDistBinsToPath]
      ["mate-docs", "api.html"]

  "build" ~> (need $ "bdist-py" : "bdist-go" : (bDistRoot </> "local/share/default-signatures.yml") : (bDistRoot </> "local/lib" <*/> map takeFileName mateSOs))

  (buildRoot </> "llvm" <*/> mateSOs) &%> \_ -> do
    need [bDistAbs </> "llvm-wedlock/.stamp"]
    need =<< getDirectoryFiles sourceRoot [ "llvm//*.cpp"
                                          , "llvm//*.h"
                                          , "llvm//CMakeLists.txt"
                                          , "llvm//*.dl"
                                          , "llvm//*.hpp"
                                          ]

    cmakeBuild (buildRoot </> "llvm") Nothing

  -- NOTE(ww): Create a ".stamp" file to ensure that we copy everything in
  -- llvm-wedlock before starting a dependent target.
  (bDistAbs </> "llvm-wedlock/.stamp") %> \_ -> do
    let llvmWedlock = "/opt/llvm-wedlock"
    llvmWedlockFiles <- getDirectoryFiles llvmWedlock ["//*"]

    forM_ llvmWedlockFiles $ \llvmWedlockFile -> do
      copyFileChanged
        (llvmWedlock </> llvmWedlockFile)
        (bDistAbs </> "llvm-wedlock" </> llvmWedlockFile)

    cmd_ [Cwd (bDistAbs </> "llvm-wedlock")] ["touch", ".stamp"]

  let needPAFiles =
        need =<< getDirectoryFiles sourceRoot [ "llvm//CMakeLists.txt"
                                              , "llvm/PointerAnalysis/*.cpp"
                                              , "llvm/PointerAnalysis/*.h"
                                              , "llvm/PointerAnalysis/*.dl"
                                              , "llvm/PointerAnalysis/*.hpp"
                                              ]

  let factgenExe = buildRoot </> "llvm/PointerAnalysis/PointerAnalysis/factgen-exe"

  factgenExe %> \_ -> do
    needPAFiles
    cmakeBuild (buildRoot </> "llvm/PointerAnalysis") (Just "factgen-exe")

  let runSouffle projFile = do
        let projFilePath = "llvm/PointerAnalysis/datalog/" ++ projFile
        need [sourceRoot </> projFilePath]
        needPAFiles
        need [factgenExe]
        (contextSensitivity:ll:rest) <- pure arguments
        let paCache = cacheRoot </> "pointer-analysis"
        let factsDir = paCache </> (takeFileName ll ++ ".facts")
        let rmIfExists path = liftIO $ do
              exists <- doesPathExist path
              when exists (removeDirectoryRecursive path)
        rmIfExists factsDir
        liftIO $ createDirectoryIfMissing True paCache
        cmd_ [ factgenExe
            , "--out-dir"
            , factsDir
            , "--context-sensitivity"
            , contextSensitivity
            , ll
            ]
        let resultsDir = paCache </> (takeFileName ll ++ ".results")
        rmIfExists resultsDir
        liftIO $ createDirectoryIfMissing True resultsDir
        numProcs <- shakeThreads <$> getShakeOptions
        cmd_ $ [ "souffle"
              , "-PSIPS:max-bound" -- This should match whatever is in CMakeLists
              , "-j"
              , show numProcs
              , projFilePath
              , "-F"
              , factsDir
              , "-D"
              , resultsDir
              ] ++ rest

  "run-souffle"             ~> runSouffle "debug.project"
  "run-souffle-unification" ~> runSouffle "unification.project"
  "run-souffle-subset"      ~> runSouffle "subset.project"

  "pytests" ~> do
    numProcs <- shakeThreads <$> getShakeOptions
    callPytest False $ concat $
      [ [ "--junitxml=" ++ buildRoot </> "pytests.junit.xml"
        , "--durations=0"
        ]
      , if numProcs > 1 then [ "-n" ++ show numProcs ] else []
      , arguments
      , [ "dwarflang"
        , "frontend/test"
        ]
      ]

  "bench" ~> do
    callPytest True (pythonBenchDirs ++ arguments)

  "bench-compare" ~> do
    liftIO $ createDirectoryIfMissing True benchmarkCache
    -- removeFilesAfter benchmarkCache ["//*"]
    let bench = callPytest True . (arguments ++)
    let first = benchmarkCache </> "first.json"
    let second = benchmarkCache </> "second.json"
    bench $ pythonBenchDirs ++ [ "--benchmark-save=first"
                               , "--benchmark-json=" ++ first
                               ]
    case BuildConfig.benchCompareCmd buildConfig of
      Just cmdline -> cmd_ cmdline
      Nothing -> pure ()
    bench $ pythonBenchDirs ++ [ "--benchmark-save=second"
                               , "--benchmark-json=" ++ second
                               ]
    cmd_
      "pytest-benchmark"
      [ "compare"
      , "--histogram=" ++ benchmarkCache </> "report"
      , "--csv=" ++ benchmarkCache </> "report.csv"
      , "--group-by=name"
      , "--columns=median,mean,rounds"
      , first
      , second
      ]

  "dwarfcore-tests" ~> do
    numProcs <- shakeThreads <$> getShakeOptions
    callPytest False $ concat $
      [ [ "tests/dwarfcore", "--benchmark-disable" ]
      , if numProcs > 1 then [ "-n", show numProcs ] else []
      , arguments
      ]

  "mantiserve-tests" ~> do
    numProcs <- shakeThreads <$> getShakeOptions
    callPytest False $ concat $
      [ [ "tests/mantiserve", "tests/integration/mantiserve", "--benchmark-disable" ]
      , if numProcs > 1 then [ "-n", show numProcs ] else []
      , arguments
      ]

  "poi-tests" ~> do
    numProcs <- shakeThreads <$> getShakeOptions
    callPytest False $ concat $
      [ [ "tests/integration/poi", "--benchmark-disable" ]
      , if numProcs > 1 then [ "-n", show numProcs ] else []
      , arguments
      ]

  "postgres-tests" ~> do
    numProcs <- shakeThreads <$> getShakeOptions
    callPytest False $ concat $
      [ [ "tests/postgres", "--benchmark-disable" ]
      , if numProcs > 1 then [ "-n", show numProcs ] else []
      , arguments
      ]

  "//*/*.bc" %> \bcRel -> do
    bcAbs <- liftIO $ makeAbsolute bcRel
    let prog = dropExtension bcAbs

    e <- doesFileExist (prog <.> "ll")
    if e
      then do
        removeIfExists bcAbs
        need [prog <.> "ll"]

        opqFlags <- opaque "llvm"

        cmd_ "llvm-as" opqFlags
          [ "-o", prog <.> "bc"
          , prog <.> "ll"
          ]
        produces [prog <.> "bc"]
      else produces [prog <.> "bc"]

  "format-black" ~>
    lint
      needHasChangedFunc
      (pure ["dev-requirements.txt", "pyproject.toml"])
      getPythonFiles
      (Right (\files -> cmd_ "black" files))

  "format-docformatter" ~>
    lint
      needHasChangedFunc
      (pure ["dev-requirements.txt", "pyproject.toml"])
      getPythonFiles
      (Right (\files -> cmd_ "docformatter --in-place --wrap-summaries 100 --wrap-descriptions 100" files))

  "format-isort" ~>
    lint
      needHasChangedFunc
      (pure ["dev-requirements.txt", "pyproject.toml"])
      getPythonFiles
      (Right (\files -> cmd_ "isort" files))

  "format-clang-format" ~>
    lint
      needHasChangedFunc
      (pure ["Dockerfile", "llvm/.clang-format"])
      getAllCPPFiles
      (Left (\file -> cmd_ "clang-format" ["-i", file]))

  "format-cmake" ~>
    lint
      needHasChangedFunc
      (pure ["dev-requirements.txt"])
      getCMakeFiles
      (Right (\files -> cmd (["cmake-format", "--in-place"] ++ files)))

  "format" ~> need (map ("format-" ++) ["black", "isort", "clang-format", "cmake", "docformatter"])

  "lint-sh" ~> do
    let shellScriptDirs =
          [ "build-tests/"
          , "ci/"
          , "dwarfcore/tests/"
          ]
    lint
      needHasChangedFunc
      (pure ["Dockerfile", ".shellcheckrc"])
      (getFilesWithExtensionsInDirs ["sh"] shellScriptDirs [])
      (Left (\file -> cmd_ "shellcheck" [file]))

  "lint-py-bellybutton" ~>
    lintDir
      needHasChangedFunc
      (pure ["dev-requirements.txt", "frontend/.bellybutton.yml"])
      (getFilesWithExtensionsInDirs ["py"] ["frontend"] [])
      (cmd_ [Cwd "frontend"] ["bellybutton", "lint"])

  "lint-py-black" ~>
    lint
      needHasChangedFunc
      (pure ["dev-requirements.txt", "pyproject.toml"])
      getPythonFiles
      (Right (\files -> cmd_ "black" ("--check" : files)))

  "lint-py-isort" ~>
    lint
      needHasChangedFunc
      (pure ["dev-requirements.txt", "pyproject.toml"])
      getPythonFiles
      (Right (\files -> cmd_ "isort" ("--check" : files)))

  "lint-py-docformatter" ~>
    lint
      needHasChangedFunc
      (pure ["dev-requirements.txt", "pyproject.toml"])
      getPythonFiles
      (Right (\files -> cmd_ "docformatter --check --wrap-summaries 100 --wrap-descriptions 100" files))

  let lintPyMypyPackage dir =
        ("lint-py-mypy-" ++ takeBaseName dir) ~> do
          let strip prefix list = fromMaybe list (L.stripPrefix prefix list)
          lint
            needHasChangedFunc
            (pure ["dev-requirements.txt", dir </> "mypy.ini"])
            (let pythonShebangFiles fs = case fs of
                   [] -> return []
                   (f:fs') -> do
                     shebangLine <- (head . lines) <$> liftIO (readFile f)
                     ((if "python" `L.isInfixOf` shebangLine then [f] else [])++) <$> pythonShebangFiles fs'
             in getDirectoryFiles "" [dir </> "bin//*"] >>= pythonShebangFiles)
            (Right
              (\files -> cmd_ [Cwd dir] (["mypy", "--sqlite-cache", "--scripts-are-modules"] ++
                           map (strip "/" . strip dir) files)))
          lintDir
            needHasChangedFunc
            (pure ["dev-requirements.txt", dir </> "mypy.ini"])
            (getFilesWithExtensionsInDirs
                ["py"]
                [dir, dir </> "test", dir </> "tests"]
                [])
            (cmd_ [Cwd dir] ["mypy", "--sqlite-cache", "."])

  let pythonPackages =
        [ "dwarflang"
        , "frontend/mate-common"
        , "frontend/mate-rest-client"
        , "frontend/mate-cli"
        , "frontend/mate-query"
        , "frontend/mate"
        , "mantiserve"
        , "dwarfcore"
        ]
  mapM_ lintPyMypyPackage pythonPackages

  "lint-py-mypy-tests" ~> do
    let testConfig = "dwarfcore/mypy.ini"
    lint
      needHasChangedFunc
      (pure ["dev-requirements.txt", testConfig])
      (filter (not . ("conftest.py" `L.isSuffixOf`)) <$>
         getFilesWithExtensionsInDirs ["py"] ["tests"] [])
      (Right
         (\files -> cmd_ ([ "mypy", "--sqlite-cache", "--config-file=" ++ testConfig ] ++ files)))

  "lint-py-mypy-scripts" ~> do
    let scripts = ["conftest.py"]
    let scriptConfig = "dwarfcore/mypy.ini"
    lint
      needHasChangedFunc
      (pure ["dev-requirements.txt", scriptConfig])
      (pure scripts)
      (Right
         (\files -> cmd_ ([ "mypy", "--config-file=" ++ scriptConfig ] ++ files)))

  "lint-py-mypy" ~>
    need (map (("lint-py-mypy-" ++) . takeBaseName)
              ("tests" : "scripts": pythonPackages))

  "lint-py-pylint" ~>
    lint
      needHasChangedFunc
      (pure ["dev-requirements.txt", ".pylintrc"])
      getPythonFiles
      (Right (\files -> cmd_ (["pylint"] ++ files)))

  "lint-py" ~> need (map ("lint-py-" ++) ["bellybutton", "black", "isort", "mypy", "pylint", "docformatter"])

  "lint-cmake" ~> do
    let config = ".cmake-lint.yaml"
    lint
      needHasChangedFunc
      (pure ["dev-requirements.txt", config])
      getCMakeFiles
      (Right
         (\files ->
            cmd_ $ ["cmake-lint", "--config-files", config, "--"] ++ files))

  "lint-cpp-clang-format" ~>
    lint
      needHasChangedFunc
      (pure ["Dockerfile", "llvm/.clang-format"])
      getCPPFiles
      (Left
         (\file ->
            cmd_ Shell $ unwords ["clang-format", file, "|", "diff", file, "-"]))

  (buildRoot </> "llvm/compile_commands.json") %> \_ -> do
    need =<< getCMakeFiles
    cmakeConfigure (buildRoot </> "llvm")

  "lint-cpp-clang-tidy" ~> do
    need [buildRoot </> "llvm/compile_commands.json"]
    lint
      needHasChangedFunc
      (L.foldl' (++) ["Dockerfile"] <$>
         sequence
           [ getFilesWithExtensionsInDirs ["txt"] ["llvm"] []
           , getFilesWithExtensionsInDirs ["clang-tidy"] ["llvm"] []
           ])
      getCPPFiles
      (Left
         (\file ->
            cmd_ ["clang-tidy-10", "-quiet", "-fix", "-p=" ++ (buildRoot </> "llvm"), file]))

  "lint-cpp" ~> need ["lint-cpp-clang-format", "lint-cpp-clang-tidy"]

  "lint-dockerfile" ~> do
    lint
      needHasChangedFunc
      (pure ["Dockerfile", ".hadolint.yaml"])
      (pure ["Dockerfile"])
      (Left (\file -> cmd_["hadolint", file]))

  "lint" ~> need [ "lint-sh"
                 , "lint-py"
                 , "lint-cpp"
                 , "lint-cmake"
                 , "lint-dockerfile"
                 ]

  where
    forP_ :: [a] -> (a -> Action b) -> Action ()
    forP_ xs f = void (forP xs f)

    removeIfExists path = do
      exists <- doesFileExist path
      liftIO $ when exists (removeFile path)

    pythonBenchDirs = ["frontend"]
    pythonDirs = [ "doc"
                 , "tests"
                 , "dwarfcore"
                 , "mantiserve"
                 , "dwarflang"
                 , "pysmt2lib"
                 ] ++ pythonBenchDirs

    getFilesWithExtensionsInDirs extensions dirs except =
      filter (`notElem` except) . concat <$>
        (forP extensions $ \extension ->
          getDirectoryFiles "" ((<//> ("*." ++ extension)) <$> dirs))

    getPythonFiles =
      (++)
      <$> getFilesWithExtensionsInDirs
            ["py"]
            pythonDirs
            []
      <*> needHasChanged ["frontend/mate/bin/mate", "conftest.py"]

    cppExtensions = ["cpp", "c", "hpp", "h"]

    -- Not including tests or pointer analysis submodule
    getCPPFiles =
      getFilesWithExtensionsInDirs
        cppExtensions
        ["llvm/headache", "llvm/MATE", "llvm/nomina"]
        []

    -- Including tests
    getAllCPPFiles =
      (++)
      <$> getCPPFiles
      <*> getFilesWithExtensionsInDirs
            cppExtensions
            ["frontend/test/programs"]
            []

    getCMakeFiles =
      filter ("CMakeLists.txt" `L.isSuffixOf`)
        <$> getFilesWithExtensionsInDirs ["txt"] ["llvm"] []

parseRawArguments :: [String] -> ([String], [String])
parseRawArguments rawArguments = case span (/= "--") rawArguments of
  (ts, []) -> (ts, [])
  (ts, ("--":as)) -> (ts, as)
  _ -> error "Unreachable arguments sequence."

localPythonPackage :: FilePath -> FilePath -> HybridRule
localPythonPackage sourcePackagePath targetPackagePath =
  let targetPattern = targetPackagePath <//> "*.py"
  in do
    -- Generic Rule
    targetPattern %> \packageFile ->
      let Just [relativeDir, relativeFile] = filePattern targetPattern packageFile
      in copyFile' (sourcePackagePath </> relativeDir </> relativeFile <.> "py") packageFile

    return $ (targetPackagePath <*/>) <$> getDirectoryFiles sourcePackagePath ["//*.py"]


(<*/>) :: FilePath -> [FilePath] -> [FilePath]
(<*/>) prefix suffixes = [prefix </> suffix | suffix <- suffixes]

infixr 3 <*/>
