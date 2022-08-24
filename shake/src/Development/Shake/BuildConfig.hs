{-
Module           : Development.Shake.BuildConfig
Copyright        : (c) Galois, Inc 2022
Maintainer       : Langston Barrett <langston@galois.com>
Stability        : provisional

This module configures the build system's command line flags. These flags can
only be accessed via Shake Oracles, which ensures that when they change, rules
that depend on them will be rerun.
-}

{-# LANGUAGE DeriveAnyClass #-}
{-# LANGUAGE DeriveGeneric #-}
{-# LANGUAGE StandaloneDeriving #-}
{-# LANGUAGE TypeFamilies #-}

module Development.Shake.BuildConfig
  ( setupOpaqueOracle
  , setupReleaseBuildOracle
  , setupScanBuildOracle
  , setupSanitizerOracle
  , Sanitizer(..)
  , sanitizerCMakeFlags
  , BuildConfig
  , out
  , benchCompareCmd
  , defaultBuildConfig
  , buildFlags
  ) where

import Control.Monad (void)
import Data.Maybe (mapMaybe)
import qualified Data.List as L
import GHC.Generics

import System.Console.GetOpt
import Development.Shake
import Development.Shake.Classes

-- | The type of a path representing a directory, the contents under which are
-- built/managed by a different build-system.
newtype Opaque = Opaque FilePath
  deriving (Binary, Eq, Generic, Hashable, NFData, Show, Typeable)
type instance RuleResult Opaque = [CmdOption]

deriving instance Binary CmdOption
deriving instance Generic CmdOption
deriving instance Hashable CmdOption
deriving instance NFData CmdOption

setupOpaqueOracle :: Rules (FilePath -> Action [CmdOption])
setupOpaqueOracle = do
  oracle <-
    addOracle $ \(Opaque opq) ->
      case opq of
        "llvm" -> do
          getEnv "LLVM_BIN" >>= \e -> case e of
            Nothing -> return []
            Just ld -> return [AddPath [ld] []]

        _ -> putNormal ("! Expecting system-provided opaque " ++ opq) >> return []
  pure (oracle . Opaque)

-- | Compiler sanitizers
data Sanitizer
  = Address
  | Memory
  | Thread
  | Undefined
  deriving (Binary, Eq, Generic, Hashable, NFData, Show, Typeable)

newtype Sanitizers = Sanitizers ()
  deriving (Binary, Eq, Generic, Hashable, NFData, Show, Typeable)
type instance RuleResult Sanitizers = [Sanitizer]

readSanitizers :: String -> [Sanitizer]
readSanitizers s = mapMaybe readSanitizer (split ',' s)
  where

    readSanitizer :: String -> Maybe Sanitizer
    readSanitizer "address" = Just Address
    readSanitizer "memory" = Just Memory
    readSanitizer "thread" = Just Thread
    readSanitizer "undefined" = Just Undefined
    readSanitizer _ = Nothing

    split :: Char -> String -> [String]
    split c s =
      case rest of
        [] -> [chunk]
        _:rest -> chunk : split c rest
      where (chunk, rest) = break (==c) s

sanitizerFlag :: Sanitizer -> String
sanitizerFlag Address = "-fsanitize=address"
sanitizerFlag Memory = "-fsanitize=memory"
sanitizerFlag Thread = "-fsanitize=thread"
sanitizerFlag Undefined = "-fsanitize=undefined -fno-sanitize=vptr" -- HACK

sanitizerCMakeFlags :: [Sanitizer] -> [String]
sanitizerCMakeFlags [] = []
sanitizerCMakeFlags sanitizers =
  let buildAndLinkFlags = (map sanitizerFlag sanitizers)
      buildFlags =
        -- The LLVM documentation recommends using these flags for ASan.
        if Address `elem` sanitizers
        then ["-O1", "-fno-omit-frame-pointer"]
        else []
  in [ "-DCMAKE_C_FLAGS=" ++ L.intercalate " " (buildAndLinkFlags ++ buildFlags)
     , "-DCMAKE_CXX_FLAGS=" ++ L.intercalate " " (buildAndLinkFlags ++ buildFlags)
     , "-DLDFLAGS=" ++ L.intercalate " " buildAndLinkFlags
     ]

data BuildConfig = BuildConfig
  { out :: FilePath
  , useScanBuild :: Bool
  , useSanitizers :: [Sanitizer]
  , releaseBuild :: Bool
  , benchCompareCmd :: Maybe String
  }

defaultBuildConfig :: BuildConfig
defaultBuildConfig = BuildConfig
  { out = ".out"
  , useScanBuild = False
  , useSanitizers = []
  , releaseBuild = False
  , benchCompareCmd = Nothing
  }

buildFlags :: [OptDescr (Either String (BuildConfig -> BuildConfig))]
buildFlags =
  [ Option ['o'] ["out"] (ReqArg (\p -> Right $ \bc -> bc { out = p }) "PATH")
      "Path to build output directory, relative to source root (or absolute)."
  , Option [] ["scan-build"] (NoArg (Right $ \bc -> bc { useScanBuild = True }))
      "Use the Clang static analyzer while compiling LLVM passes."
  , Option [] ["sanitize"]
      (ReqArg (\a -> (Right $ \bc -> bc { useSanitizers = readSanitizers a })) "SAN")
      "Build with LLVM sanitizers (comma-separated list)."
  , Option [] ["release-build"] (NoArg (Right $ \bc -> bc { releaseBuild = True }))
      "Build for a release (i.e. disable assertions, optimize aggressively)."
  , Option [] ["bench-compare-cmd"]
      (ReqArg (\c -> Right $ \bc -> bc { benchCompareCmd = Just c }) "CMD")
      "Command to run in between bench-compare runs (usually `git checkout`)."
  ]

setupSanitizerOracle :: BuildConfig -> Rules (Action [Sanitizer])
setupSanitizerOracle buildConfig = do
  void $ addOracle $ \(Sanitizers _) -> return $ useSanitizers buildConfig
  pure (askOracle (Sanitizers ()))

newtype ReleaseBuild = ReleaseBuild ()
  deriving (Binary, Eq, Generic, Hashable, NFData, Show, Typeable)
type instance RuleResult ReleaseBuild = Bool

setupReleaseBuildOracle :: BuildConfig -> Rules (Action Bool)
setupReleaseBuildOracle buildConfig = do
  void $ addOracle $ \(ReleaseBuild _) -> return $ releaseBuild buildConfig
  pure (askOracle (ReleaseBuild ()))

newtype ScanBuild = ScanBuild ()
  deriving (Binary, Eq, Generic, Hashable, NFData, Show, Typeable)
type instance RuleResult ScanBuild = Bool

setupScanBuildOracle :: BuildConfig -> Rules (Action Bool)
setupScanBuildOracle buildConfig = do
  void $ addOracle $ \(ScanBuild _) -> return $ useScanBuild buildConfig
  pure (askOracle (ScanBuild ()))
