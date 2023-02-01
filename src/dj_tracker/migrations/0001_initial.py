import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Field",
            fields=[
                (
                    "cache_key",
                    models.BigIntegerField(primary_key=True, serialize=False),
                ),
                ("name", models.CharField(max_length=255)),
            ],
            options={
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="FieldTracking",
            fields=[
                (
                    "cache_key",
                    models.BigIntegerField(primary_key=True, serialize=False),
                ),
                ("get_count", models.PositiveIntegerField(default=0)),
                ("set_count", models.PositiveIntegerField(default=0)),
                (
                    "field",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="trackings",
                        to="dj_tracker.field",
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="InstanceFieldTracking",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("num_occurrences", models.PositiveIntegerField()),
                (
                    "field_tracking",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="dj_tracker.fieldtracking",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="InstanceTracking",
            fields=[
                (
                    "cache_key",
                    models.BigIntegerField(primary_key=True, serialize=False),
                ),
                ("select_related_field", models.CharField(blank=True, max_length=255)),
                (
                    "field_trackings",
                    models.ManyToManyField(
                        through="dj_tracker.InstanceFieldTracking",
                        to="dj_tracker.fieldtracking",
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="Model",
            fields=[
                (
                    "cache_key",
                    models.BigIntegerField(primary_key=True, serialize=False),
                ),
                ("label", models.CharField(max_length=255)),
            ],
            options={
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="Query",
            fields=[
                (
                    "cache_key",
                    models.BigIntegerField(primary_key=True, serialize=False),
                ),
                ("average_duration", models.PositiveIntegerField(null=True)),
                ("cache_hits", models.PositiveSmallIntegerField(null=True)),
                ("iterable_class", models.CharField(blank=True, max_length=64)),
                (
                    "query_type",
                    models.CharField(
                        choices=[
                            ("COUNT", "Count"),
                            ("SELECT", "Select"),
                            ("EXISTS", "Exists"),
                        ],
                        max_length=6,
                    ),
                ),
                ("depth", models.PositiveSmallIntegerField(default=0)),
                ("attributes_accessed", models.JSONField(null=True)),
                ("len_calls", models.PositiveSmallIntegerField(null=True)),
                ("exists_calls", models.PositiveSmallIntegerField(null=True)),
                ("contains_calls", models.PositiveSmallIntegerField(null=True)),
                ("num_instances", models.PositiveIntegerField()),
                (
                    "field",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="dj_tracker.field",
                    ),
                ),
                (
                    "instance_trackings",
                    models.ManyToManyField(to="dj_tracker.instancetracking"),
                ),
                (
                    "model",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="dj_tracker.model",
                    ),
                ),
                (
                    "related_queryset",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="related_querysets",
                        to="dj_tracker.query",
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="QueryGroup",
            fields=[
                (
                    "cache_key",
                    models.BigIntegerField(primary_key=True, serialize=False),
                ),
            ],
            options={
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="Request",
            fields=[
                (
                    "cache_key",
                    models.BigIntegerField(primary_key=True, serialize=False),
                ),
                ("method", models.CharField(max_length=8)),
                ("content_type", models.CharField(max_length=256)),
                ("query_string", models.CharField(max_length=1024)),
            ],
            options={
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="SourceCode",
            fields=[
                (
                    "cache_key",
                    models.BigIntegerField(primary_key=True, serialize=False),
                ),
                ("lineno", models.PositiveIntegerField()),
                ("code", models.TextField()),
                ("func", models.CharField(blank=True, max_length=255)),
            ],
            options={
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="SourceFile",
            fields=[
                (
                    "cache_key",
                    models.BigIntegerField(primary_key=True, serialize=False),
                ),
                ("name", models.CharField(max_length=255)),
            ],
            options={
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="SQL",
            fields=[
                (
                    "cache_key",
                    models.BigIntegerField(primary_key=True, serialize=False),
                ),
                ("sql", models.TextField()),
            ],
            options={
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="StackEntry",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("index", models.PositiveSmallIntegerField()),
                (
                    "source",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="entries",
                        to="dj_tracker.sourcecode",
                    ),
                ),
            ],
            options={
                "ordering": ("index",),
            },
        ),
        migrations.CreateModel(
            name="URLPath",
            fields=[
                (
                    "cache_key",
                    models.BigIntegerField(primary_key=True, serialize=False),
                ),
                ("path", models.CharField(max_length=1024)),
            ],
            options={
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="Tracking",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("started_at", models.DateTimeField()),
                (
                    "query_group",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="trackings",
                        to="dj_tracker.querygroup",
                    ),
                ),
                (
                    "request",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="trackings",
                        to="dj_tracker.request",
                    ),
                ),
            ],
            options={
                "ordering": ("-started_at",),
            },
        ),
        migrations.CreateModel(
            name="Traceback",
            fields=[
                (
                    "cache_key",
                    models.BigIntegerField(primary_key=True, serialize=False),
                ),
                (
                    "stack",
                    models.ManyToManyField(
                        related_name="+",
                        through="dj_tracker.StackEntry",
                        to="dj_tracker.sourcecode",
                    ),
                ),
                (
                    "template_info",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="dj_tracker.sourcecode",
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
        ),
        migrations.AddField(
            model_name="stackentry",
            name="traceback",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE, to="dj_tracker.traceback"
            ),
        ),
        migrations.AddField(
            model_name="sourcecode",
            name="filename",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE, to="dj_tracker.sourcefile"
            ),
        ),
        migrations.AddField(
            model_name="request",
            name="path",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="requests",
                to="dj_tracker.urlpath",
            ),
        ),
        migrations.CreateModel(
            name="QuerySetTracking",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("num_occurrences", models.PositiveSmallIntegerField()),
                (
                    "query",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="trackings",
                        to="dj_tracker.query",
                    ),
                ),
                (
                    "query_group",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="dj_tracker.querygroup",
                    ),
                ),
            ],
        ),
        migrations.AddField(
            model_name="querygroup",
            name="queries",
            field=models.ManyToManyField(
                through="dj_tracker.QuerySetTracking", to="dj_tracker.query"
            ),
        ),
        migrations.AddField(
            model_name="query",
            name="sql",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE, to="dj_tracker.sql"
            ),
        ),
        migrations.AddField(
            model_name="query",
            name="traceback",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE, to="dj_tracker.traceback"
            ),
        ),
        migrations.AddField(
            model_name="instancefieldtracking",
            name="instance_tracking",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="related_field_trackings",
                to="dj_tracker.instancetracking",
            ),
        ),
        migrations.AddField(
            model_name="field",
            name="model",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE, to="dj_tracker.model"
            ),
        ),
    ]
