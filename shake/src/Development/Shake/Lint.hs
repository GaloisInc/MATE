module Development.Shake.Lint where

import Control.Monad (void)

import Development.Shake

-- | Run a linter that doesn't take files as arguments
lintDir ::
  ([FilePath] -> Action [FilePath])
    {- ^ A function that determines which files have changed, and @needs@ them -}->
  Action [FilePath] {-^ List of linter configuration files  -} ->
  Action [FilePath] {-^ List of all files that are subject to linter -} ->
  Action () {-^ How to run the linter -} ->
  Action ()
lintDir needHasChangedFunc configFiles allFiles run = do
  changedConfigFiles <- needHasChangedFunc =<< configFiles
  filesToLint <-
    allFiles >>=
      if changedConfigFiles /= []
      then pure
      else needHasChangedFunc
  if [] /= (changedConfigFiles ++ filesToLint)
  then run
  else pure ()

-- | Run a linter that takes files as arguments
lint ::
  ([FilePath] -> Action [FilePath])
    {- ^ A function that determines which files have changed, and @needs@ them -}->
  Action [FilePath] {-^ List of linter configuration files  -} ->
  Action [FilePath] {-^ List of all files that are subject to linter -} ->
  (Either (FilePath -> Action ()) ([FilePath] -> Action ()))
    {-^ Command-line to run for a given file (individual or collective) -} ->
  Action ()
lint needHasChangedFunc configFiles allFiles buildCommand = do
  changedConfigFiles <- needHasChangedFunc =<< configFiles
  -- If the linter configuration changed, re-lint everything.
  filesToLint <-
    allFiles >>=
      if changedConfigFiles /= []
      then pure
      else needHasChangedFunc
  case buildCommand of
    Left oneAtATime -> void $ forP filesToLint oneAtATime
    Right allAtOnce ->
      if filesToLint /= []
      then allAtOnce filesToLint
      else pure ()

