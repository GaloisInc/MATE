{-# LANGUAGE LambdaCase #-}
{-# LANGUAGE OverloadedStrings #-}

module Development.Shake.Changes where

import           Data.Maybe (fromMaybe)
import qualified Data.Set as Set
import           System.Environment (lookupEnv)
import           System.Exit (ExitCode(ExitSuccess))
import           System.Process (readProcessWithExitCode)

import           Development.Shake

changedBetweenRevisions :: String -> String -> IO (Maybe (Set.Set FilePath))
changedBetweenRevisions rev1 rev2 =
  fmap
    (\case
      (ExitSuccess, stdout, "") -> Just $ Set.fromList (lines stdout)
      _ -> Nothing)
    (readProcessWithExitCode "git" ["diff", "--name-only", rev1, rev2] "")

needHasChangedGit :: IO (Maybe ([FilePath] -> Action [FilePath]))
needHasChangedGit = do
  lookupEnv "CI_COMMIT_SHA" >>=
    \case
      Just sha ->
        changedBetweenRevisions sha "origin/master" >>=
          \case
            Just changeSet ->
              pure $
                Just $
                  pure . Set.toList . Set.intersection changeSet . Set.fromList
            _ -> pure Nothing
      _ -> pure Nothing

-- | Return a function that either consults the Shake database (locally) or git
-- (in Gitlab CI), with functionality similar to 'needHasChanged'.
getNeedHasChangedFunc :: IO ([FilePath] -> Action [FilePath])
getNeedHasChangedFunc = fromMaybe needHasChanged <$> needHasChangedGit
