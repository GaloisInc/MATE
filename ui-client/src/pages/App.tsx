import { BrowserRouter as Router, Switch, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "react-query";

import { Builds } from "./Builds";
import { Compilations } from "./Compilations";
import { PointsOfInterest } from "./PointsOfInterest";
import { FlowFinder } from "./FlowFinder";
import { Snapshots } from "./Snapshots";
import "../styles/App.scss";
import { Manticore } from "./Manticore";

const flowfinder_path: string[] = [
  "/flow-finder/:buildId/snapshot/:snapshotId/:poiId?",
  "/flow-finder/:buildId/poi/:poiId",
  "/flow-finder/:buildId",
];

const queryClient = new QueryClient();

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <Router>
        <Switch>
          <Route
            path="/rest-api"
            render={() => {
              window.location.replace(
                `${window.location.protocol}//${window.location.hostname}:8666/api/v1`
              );
              return null;
            }}
          />
          <Route
            path="/notebooks"
            render={() => {
              window.location.replace(
                `${window.location.protocol}//${window.location.hostname}:8889/`
              );
              return null;
            }}
          />
          <Route path="/pois/:buildId">
            <PointsOfInterest />
          </Route>
          <Route path="/builds">
            <Builds />
          </Route>
          <Route path="/compilations">
            <Compilations />
          </Route>
          <Route path="/snapshots">
            <Snapshots />
          </Route>
          <Route path="/manticore/:buildId/:poiId?">
            <Manticore />
          </Route>
          <Route path={flowfinder_path}>
            <FlowFinder />
          </Route>
          <Route path="/">
            <Builds />
          </Route>
        </Switch>
      </Router>
    </QueryClientProvider>
  );
}

export default App;
