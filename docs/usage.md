# Usage

This page shows how to use `dj_tracker` to optimise your queries. We assume that you've already followed the steps in [Installation](./installation.md).

Run `manage.py runserver --noreload` and visit some URLs to have some trackings.

## Dashboard

The trackings dashboard is available at `/dj_tracker/`. It shows the latest and most visited URLs along with various insights into your queries.

![dj-tracker dashboard](images/dashboard.jpg)

## Requests

When you click in one of the requests shown in the dashboard, it will redirect to page showing the different query groups for that request along with how much time they occured.

![dj-tracker request](images/request.jpg)

## Query groups

Clicking on one of the query groups displayed in a request's page will show all the queries in that group with some statistics associated to them. It also gives the ability to only show duplicate queries or queries that induced other ones (`Related queries`).

![dj-tracker query-group](images/query-group.png)

## Query

Clicking o of the queries displayed in query group will display various information about a query: the traceback, the SQL generated, fields usage but also hints on how to improve the query:

![dj-tracker query](images/query.png)
