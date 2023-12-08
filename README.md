# Firelink
A GUI webapp wrapper about Bonfire. Allows developers to interact with and deploy apps to Ephemeral Environments via a friendly graphical interface.

## Config
You need to set your oc token and server via the `OC_TOKEN` and `OC_SERVER` environment variables before starting the app.
```
$ export OC_TOKEN="sha256~DEADBEEFDEADBEEFDEADBEEFDEADBEEF"
$ export OC_SERVER="https://api.secretlab.company.com:6443"
```


## Development Setup
Here's how you can get all the parts set up for development
```bash
# Make sure you have pip and pipenv installed before these obviously
$ pipenv install
$ pipenv shell
# You'll need to start these in different terminals to capture their logs
$ make start-server
$ make start-ui
$ sudo make start-proxy
```

The frontend runs on port 3000. The backend runs on port 5000. The dev proxy runs on port 8080 and routes the correct requests to the backend and frontend. This ensures that when you'd doing fullstack development the environment you're running on looks like produciton, with everything served out from port 8080.

Yeah yeah I know environment variables and conditionality are available as options but I would rather run a goofy little proxy that introduce runtime conditionality.

# Building for Production
```bash
$ make build
```

Will result in an image that serves out both the compiled frontend app and run the backend service. This is unusual at Red Hat. We could seperate the frontend from the backend in the future and make this a consoledot app. However, in the short term and to get things going it is a LOT faster and easier to do everything in one ap