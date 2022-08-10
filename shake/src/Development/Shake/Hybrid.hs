module Development.Shake.Hybrid where

import Development.Shake

-- A computation that does two things:
--   - Establishes /backwards/ rules (side-effects)
--   - Returns a forward action which enumerates the set of files we should
--     expect to be built by the backwards rules
type HybridRule = Rules (Action [FilePath])

-- Given a list of hybrid rules, run them all to register the backwards rules,
-- and return a computation that runs all of the forward actions and
-- concatenates their results. The result of @group@ is an action which
-- produces a list of filepaths, which may be passed to @need@ in order to
-- depend on the entire group of files produces by any of the rules.
group :: [HybridRule] -> Rules (Action [FilePath])
group metaRules = do
  dependencies <- sequence metaRules
  return $ concat <$> sequence dependencies

copyRule :: FilePath -> FilePath -> HybridRule
copyRule from to = do
  to %> \_ -> copyFile' from to
  return $ return [to]
