# MATE UI Client

This is the UI client to interface to provide easy access to builds, points-of-interest and a graph-visualization tool for
supporting analysis.

## Technologies Used

This UI was initially created using [Create React App](https://github.com/facebook/create-react-app) to create the initial scaffolding. The full list of technologies/libraries used is:

- [React](https://reactjs.org/) - the UI framework
- [TypeScript](https://www.typescriptlang.org/) - "typed" JavaScript
- [React Bootstrap](https://react-bootstrap.github.io/) (which is a React-specific wrapper for [Bootstrap4](https://getbootstrap.com/docs/4.0/getting-started/introduction/)) - UI component toolkit
- [Sass](https://sass-lang.com/) - Enhanced CSS for easier styling
- [React Cytoscapejs](https://github.com/plotly/react-cytoscapejs) (which is a React-specfici wrapper for [Cytoscape](https://js.cytoscape.org/)) - Graph rendering

## Project Structure

The project is organized as such:

```
├── public - static resources used by the client
├── src - root directory for application code
|   ├── lib - ....
|   |   ├── api - logic relating to network calls to **TODO: FILL IN...**
|   ├── components - simple, reusable React components
|   ├── pages - top-level "page" React components
|   ├── styles - Sass stylesheets (typically named for the name of the React container/component they style)
|   ├── index.tsx - entry point for the application
|   ├── react-app-env.d.ts - reference type definitions created by the "react-scripts" that generated the intial code
|   ├── reportWebVitals.ts`: utilities for measuring app performance
├── .gitignore
├── package-lock.json - pins dependency versions
├── package.json - project configuration file
├── README.md - this file
├── tsconfig.json - configuration file for TypeScript
├── yarn.lock - used by yarn (alternative to npm that is added by react-scripts)
```

## Development Setup

The definition for building the Docker image for the UI can be found in the root `Dockerfile` in the `ui` stage.

There is a `docker-compose.ui.yml` at the root of the project which specifies the dependent services.

### Starting

To start up the service, run:

```bash
$ docker-compose -f docker-compose.yml -f docker-compose.ui.yml up db server storage ui
```

#### Rebuilding

If you add/remove any dependencies to the `package.json` or add/remove/change assets in `/public`, you will need to rebuild the image. You can do this by running:

```bash
$ docker-compose -f docker-compose.yml -f docker-compose.ui.yml up --no-deps --build ui
```

### Tips for development

If you are developing this application, then it is recommended that you mount your local `src` directory into the image. This allows the app to rebuild automatically when you make changes, reflecting them into the UI quickly. To do this, you need to add the following lines to `docker-compose.ui.yml`:

```
    depends_on:
      - server
      - storage
      - db
    /* ADD THE FOLLOWING */
    volumes:
      - ./ui-client/src:/ui-client/src
    /* END ADD */
networks:
```

### Running Unit Tests

There are unit tests for all the components, libraries, and hooks (but not pages since they are more integrations of the aforementioned). You can run unit tests with the following command:

```sh
$ npm test
```

This will start the test-runner in "watch" mode where it will look for changes to the test-files and the files they are testing to determine what needs to be re-run. If you want to run the tests once, you can run:

```sh
$ npm test -- --watchAll=false
```

#### Test Coverage

You can get a coverage analysis by running:

```sh
$ npm run test:coverage
```

This will run the unit tests with coverage analysis enabled, writing the output to the `coverage` directory. To explore the results in your browser, simply open the following file in your favorite browser:

```
coverage/lcov-report/index.html
```

## Create React App Background

This project was bootstrapped with [Create React App](https://github.com/facebook/create-react-app).

### Available Scripts

In the project directory, you can run:

#### `npm start`

Runs the app in the development mode.\
Open [http://localhost:3000](http://localhost:3000) to view it in the browser.

The page will reload if you make edits.\
You will also see any lint errors in the console.

#### `npm test`

Launches the test runner in the interactive watch mode.\
See the section about [running tests](https://facebook.github.io/create-react-app/docs/running-tests) for more information.

#### `npm build`

Builds the app for production to the `build` folder.\
It correctly bundles React in production mode and optimizes the build for the best performance.

The build is minified and the filenames include the hashes.\
Your app is ready to be deployed!

See the section about [deployment](https://facebook.github.io/create-react-app/docs/deployment) for more information.

#### `npm eject`

**Note: this is a one-way operation. Once you `eject`, you can’t go back!**

If you aren’t satisfied with the build tool and configuration choices, you can `eject` at any time. This command will remove the single build dependency from your project.

Instead, it will copy all the configuration files and the transitive dependencies (webpack, Babel, ESLint, etc) right into your project so you have full control over them. All of the commands except `eject` will still work, but they will point to the copied scripts so you can tweak them. At this point you’re on your own.

You don’t have to ever use `eject`. The curated feature set is suitable for small and middle deployments, and you shouldn’t feel obligated to use this feature. However we understand that this tool wouldn’t be useful if you couldn’t customize it when you are ready for it.

### Learn More

You can learn more in the [Create React App documentation](https://facebook.github.io/create-react-app/docs/getting-started).

To learn React, check out the [React documentation](https://reactjs.org/).

---

This material is based upon work supported by the United States Air Force and
Defense Advanced Research Project Agency (DARPA) under
Contract No. FA8750-19-C-0004. Any opinions, findings and conclusions or
recommendations expressed in this material are those of the author(s) and do
not necessarily reflect the views of the United States Air Force or DARPA.
