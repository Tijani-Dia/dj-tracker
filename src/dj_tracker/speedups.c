#define PY_SSIZE_T_CLEAN
#include <Python.h>


static PyObject *hash_list(PyObject *self, PyObject *args) {
    PyObject *list = NULL;
    Py_ssize_t i, n;
    long hash, value;

    if (!PyArg_ParseTuple(args, "O", &list)) {
        return NULL;
    }
    if ((n = PyList_Size(list)) < 0) {
        PyErr_SetString(PyExc_TypeError, "Argument is not a list.");
        return NULL;
    }
    for (i = 0, hash = 98767 - n * 555; i < n; i++) {
        if ((value = PyObject_Hash(PyList_GetItem(list, i))) == -1) {
            PyErr_SetString(PyExc_TypeError, "Unhashable list item.");
            return NULL;
        }
        hash = hash + i + (value % 9999999) * 1001;
    }
    return PyLong_FromLong(hash);
}

static PyObject *hash_string(PyObject *self, PyObject *args) {
    const unsigned char *str;
    unsigned long hash = 5381;
    int c;

    if (!PyArg_ParseTuple(args, "s", &str)) {
        return NULL;
    }
    while ((c = *str++)) {
        hash = (hash << 5) + hash + c; /* hash * 33 + c */
    }
    return PyLong_FromLong(hash);
}

static PyObject *hash_counter(PyObject *self, PyObject *args) {
    PyObject *counter = NULL;
    PyObject *keys = NULL;
    PyObject *key = NULL;
    Py_ssize_t i, n;
    long hash;

    if (!PyArg_ParseTuple(args, "O", &counter)) {
        return NULL;
    }

    if ((n = PyDict_Size(counter)) < 0) {
        PyErr_SetString(PyExc_TypeError, "Argument is not a counter.");
        return NULL;
    } else if (n == 0) {
        return PyLong_FromLong(98767);
    }
    if (!(keys = PyDict_Keys(counter))) {
        PyErr_SetString(PyExc_TypeError, "Error retrieving counter keys.");
        return NULL;
    }
    if (PyList_Sort(keys) != 0) {
        Py_DECREF(keys);
        PyErr_SetString(PyExc_TypeError, "Error sorting counter keys.");
        return NULL;
    }
    for (i = 0, hash = 98767 - n * 555; i < n; i++) {
        key = PyList_GetItem(keys, i);
        hash = hash + PyLong_AsLong(PyDict_GetItem(counter, key)) + (PyObject_Hash(key) % 9999999) * 1001;
    }

    Py_DECREF(keys);
    return PyLong_FromLong(hash);
}


static PyMethodDef speedups_methods[] = {
    {"hash_list",  hash_list, METH_VARARGS, "Hash a list."},
    {"hash_string",  hash_string, METH_VARARGS, "Hash a string."},
    {"hash_counter",  hash_counter, METH_VARARGS, "Hash a counter."},
    {NULL, NULL, 0, NULL}        /* Sentinel */
};

static struct PyModuleDef speedups_modules = {
    PyModuleDef_HEAD_INIT,
    "dj_tracker.speedups",   /* name of module */
    "C implementation of performance sensitive functions.",
    -1,
    speedups_methods,
    NULL,
    NULL,
    NULL,
    NULL
};

PyMODINIT_FUNC PyInit_speedups(void) {
    return PyModule_Create(&speedups_modules);
}
