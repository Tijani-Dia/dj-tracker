# `dj-tracker` tutorial

This is the source code of the [`dj-tracker` tutorial](https://tijani-dia.github.io/dj-tracker/tutorial/setup/).

Follow the instructions below to set up the project locally.

## Clone

[Clone the `dj-tracker` repository](https://github.com/Tijani-Dia/dj-tracker).

## Check out the `tutorial` directory

```console
cd dj-tracker/tutorial
```

## Virtual environment (Recommended)

Create a new `dj-tracker-tutorial` virtualenv e.g with `pyenv`:

```console
pyenv virtualenv 3.x.x dj-tracker-tutorial
```

## Install requirements

Install the project's requirements as such:

```console
pip install -r requirements.txt
```

## Run the migrations for the `default` and `trackings` databases

```console
./manage.py migrate
./manage.py migrate dj_tracker --database=trackings
```

## Populate the database

```console
./manage.py shell -c  "from app.factories import create_books; create_books(4000)"
```

**Note**: This can take a while. Feel free to adjust the number of books to create.

## Run the server

You can now run the server and make requests to the `/time/` and `/memory/` endpoints and the profiling results will be displayed when you stop the server.

I suggest commenting out the `dj_tracker` middleware in the `MIDDLEWARE` list (in `tutorial/settings.py`) when testing those endpoints to avoid noise from the worker thread.

Uncomment it when you want to see the trackings results in the dashboard.
