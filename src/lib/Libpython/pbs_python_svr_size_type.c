/*
 * Copyright (C) 1994-2019 Altair Engineering, Inc.
 * For more information, contact Altair at www.altair.com.
 *
 * This file is part of the PBS Professional ("PBS Pro") software.
 *
 * Open Source License Information:
 *
 * PBS Pro is free software. You can redistribute it and/or modify it under the
 * terms of the GNU Affero General Public License as published by the Free
 * Software Foundation, either version 3 of the License, or (at your option) any
 * later version.
 *
 * PBS Pro is distributed in the hope that it will be useful, but WITHOUT ANY
 * WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
 * FOR A PARTICULAR PURPOSE.
 * See the GNU Affero General Public License for more details.
 *
 * You should have received a copy of the GNU Affero General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 *
 * Commercial License Information:
 *
 * For a copy of the commercial license terms and conditions,
 * go to: (http://www.pbspro.com/UserArea/agreement.html)
 * or contact the Altair Legal Department.
 *
 * Altair’s dual-license business model allows companies, individuals, and
 * organizations to create proprietary derivative works of PBS Pro and
 * distribute them - whether embedded or bundled with other software -
 * under a commercial license agreement.
 *
 * Use of Altair’s trademarks, including but not limited to "PBS™",
 * "PBS Professional®", and "PBS Pro™" and Altair’s logos is subject to Altair's
 * trademark licensing policies.
 *
 */


/**
 * @file	pbs_python_svr_size_type.c
 * @brief
 * CONVENTION
 *
 *  For Types and Objects:
 *  ----------------------
 *   PPSVR   : Pbs Python Server
 *   PPSCHED : Pbs Python Scheduler
 *   PPMOM   : Pbs Python Mom
 *
 *  For methods:
 *  -----------
 *     pps_    : Pbs Python Server <?> methods
 *     ppsd_   : Pbs Python Scheduler <?> methods
 *     ppm_    : Pbs Python MOM <?> methods
 */

/*
 * --------- Python representation of a Queue Type ----------
 */
#include <pbs_config.h>   /* the master config generated by configure */
#include <pbs_python_private.h>

#include <stdio.h>
#include <unistd.h>
#include <sys/types.h>
#include <sys/param.h>
#include <memory.h>
#include <stdlib.h>
#include <pbs_ifl.h>
#include <errno.h>
#include <string.h>
#include <list_link.h>
#include <log.h>
#include <attribute.h>
#include <pbs_error.h>
#include <Long.h>

extern int  comp_size(struct attribute *, struct attribute *);
extern void from_size(struct size_value *, char *);
extern int set_size(struct attribute *, struct attribute *, enum batch_op op);
extern int to_size(char *, struct size_value *);
extern int normalize_size(struct size_value *, struct size_value *,
	struct size_value *, struct size_value *);

/*
 * ============             Internal SIZE Type            ============
 */

typedef struct {
	PyObject_HEAD
	struct size_value sz_value;
	char *str_value; /* encoded represented of the above size value */
} PPSVR_Size_Object;

extern PyTypeObject PPSVR_Size_Type;
extern PyObject * PPSVR_Size_FromSizeValue(struct size_value);

#define     PPSVR_Size_Type_Check(op)  PyObject_TypeCheck(op, &PPSVR_Size_Type)
#define     PPSVR_Size_DFLT_NAME "<unset>"

#define COPY_SIZE_VALUE(dst, src)                                           \
                do {                                                        \
                    dst.atsv_num = src.atsv_num;                            \
                    dst.atsv_shift = src.atsv_shift;                        \
                    dst.atsv_units = src.atsv_units;                        \
                } while (0)


/**
 * @brief
 *	function for server
 *	checks whether the input object is negative number.
 *
 * @param[in] il - pointer to python object (number).
 *
 * @return	int
 * @retval	1	if negative
 * @retval	0	if not
 *
 */
static int
_pps_check_for_negative_number(PyObject *il) {
	PyObject *str_value = NULL;
	char *c_value;
	int rc = 0;

	if (!(str_value = PyObject_Str(il))) {
		PyErr_Clear(); rc = -1;
		goto EXIT;
	}
	c_value = PyUnicode_AsUTF8(str_value); /* TODO, is error check needed? */
	if (c_value && (*c_value == '-')) {
		rc = 1;
	} else {
		rc = -1;
		PyErr_Clear();
		goto EXIT;
	}
EXIT:
	if (str_value)
		Py_CLEAR(str_value);
	return rc;
}

/**
 * @brief
 *	server function which encode a string
 *	FROM a PPSVR_Size_Object  structure
 *
 * @param[in] self - python object (string)
 *
 * @return	int
 * @retval	0	success
 * @retval	-1	error
 *
 */
static int
_pps_size_make_str_value(PyObject *self)
{

	PPSVR_Size_Object *working_copy = (PPSVR_Size_Object *) self;
	from_size(&working_copy->sz_value, log_buffer);
	if (working_copy->str_value)
		free(working_copy->str_value);
	if (!(working_copy->str_value = strdup(log_buffer))) {
		(void) PyErr_NoMemory();
		return -1;
	}
	return 0;
}

/**
 * @brief
 *      server function which encode a string
 *      FROM a PPSVR_Size_Object  structure
 *
 * @param[in] self - python object (string)
 *
 * @return	int
 * @retval	0 	: success was either a int or long
 * @retval	-1 	: failure
 * @retval	1 	: "from" is not a int or long python object
 */

static int
_pps_size_from_long_or_int(PyObject *self, PyObject *from)
{
	PPSVR_Size_Object *working_copy = (PPSVR_Size_Object *) self;
	u_Long l_value;

	if (PyLong_Check(from)) {
		if (_pps_check_for_negative_number(from) > 0) {
			PyErr_SetString(PyExc_TypeError, "_size instance cannot be negative");
			return -1;
		}
		l_value = PyLong_AsUnsignedLongLongMask(from);
		if (PyErr_Occurred())
			return -1;
		/* good no error */
		working_copy->sz_value.atsv_num = l_value;
		working_copy->sz_value.atsv_units = ATR_SV_BYTESZ;
		working_copy->sz_value.atsv_shift = 0;
		if ((_pps_size_make_str_value(self) != 0))
			return -1;
	} else if (PyLong_Check(from)) {
		if (_pps_check_for_negative_number(from) > 0) {
			PyErr_SetString(PyExc_TypeError, "_size instance cannot be negative");
			return -1;
		}
		l_value = PyLong_AsUnsignedLongLongMask(from);
		if (PyErr_Occurred())
			return -1;
		/* good no error */
		working_copy->sz_value.atsv_num = l_value;
		working_copy->sz_value.atsv_units = ATR_SV_BYTESZ;
		working_copy->sz_value.atsv_shift = 0;
		if ((_pps_size_make_str_value(self) != 0))
			return -1;
	} else {
		return 1;
	}

	return 0;
}

/**
 * @brief
 *	decodes and assigns value(from) to size value structure(self)
 *	and encodes the PPSVR_Size_Object structure(self).
 *
 * @param[out] self - python object(server size object)
 * @param[in] from - size string to be decoded and assigned
 *
 * @return	int
 * @retval	0	success was either a int or long
 * @retval	-1	failure
 * @retval	1	"from" is not a string python object
 *
 */

static int
_pps_size_from_string(PyObject *self, PyObject *from)
{

	PPSVR_Size_Object *working_copy = (PPSVR_Size_Object *) self;
	if (PyUnicode_Check(from)) {
		if ((to_size(PyUnicode_AsUTF8(from), &working_copy->sz_value) != 0)) {
			snprintf(log_buffer, LOG_BUF_SIZE-1, "%s: bad value for _size",
				pbs_python_object_str(from));
			PyErr_SetString(PyExc_TypeError, log_buffer);
			return -1;
		}
		if ((_pps_size_make_str_value(self) != 0))
			return -1;
	} else {
		return 1;
	}
	return 0;
}

/* -----                  PyTypeObject Methods                     ----- */

/**
 * @brief
 *	creates a python object size_value structure.
 *
 * @param[in] type - pointer to size_value structure
 * @param[in] args - size_value (NULL since new)
 * @param[in] kwds - str_value (NULL since new)
 *
 * @return	structure handle
 * @retval	pointer to size_val structure	success
 */
static PyObject *
pps_size_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
	PPSVR_Size_Object * self = NULL;
	self = (PPSVR_Size_Object *) type->tp_alloc(type, 0);
	if (self) {
		memset(&self->sz_value, 0, sizeof(self->sz_value));
		self->str_value = NULL;
	}
	return (PyObject *) self;
}

/**
 * @brief
 *	initializes the size_value structure.
 *
 * @param[out] self - pointer to size_value structure
 * @param[in] args - size_value
 * @param[in] kwds - size_str
 *
 * @return	int
 * @retval	0	success
 * @retval	-1	error
 *
 */
static int
pps_size_init(PPSVR_Size_Object *self, PyObject *args, PyObject *kwds)
{

	static char *kwlist[] = {"value", NULL};
	PyObject *py_arg0 = NULL;
	int rc;

	if (!PyArg_ParseTupleAndKeywords(args, kwds,
		"O:_size.__init__",
		kwlist,
		&py_arg0
		)
		) {
		return -1;
	}

	if (PPSVR_Size_Type_Check(py_arg0)) {
		/* size object received , deep copy */
		COPY_SIZE_VALUE(self->sz_value, ((PPSVR_Size_Object *)py_arg0)->sz_value);
		if (self->str_value)
			free(self->str_value);
		if (!(self->str_value =
			strdup(((PPSVR_Size_Object *)py_arg0)->str_value))) {
			(void) PyErr_NoMemory();
			return -1;
		}
		goto SUCCESSFUL_INIT;
	}
	if ((rc = _pps_size_from_string((PyObject *)self, py_arg0)) == -1) {
		return -1;
	}
	if (rc == 0)
		goto SUCCESSFUL_INIT;

	/* check for int or long */
	if ((rc = _pps_size_from_long_or_int((PyObject *)self, py_arg0)) == -1) {
		return -1;
	}
	if (rc == 0)
		goto SUCCESSFUL_INIT;

	/* at this point there is no hope */
	PyErr_SetString(PyExc_TypeError, "Bad _size value");
	return -1;

SUCCESSFUL_INIT:
	return 0;
}

/* __del__ */
/**
 * @brief
 *      free the memory for size_value structure.
 *
 * @param[out] self - pointer to size_value structure
 *
 * @return      int
 * @retval      0       success
 * @retval      -1      error
 *
 */

static void
pps_size_dealloc(PPSVR_Size_Object *self)
{
	if (self->str_value) {
		free(self->str_value);
	}
	Py_TYPE(self)->tp_free((PyObject*) self);
	return;
}

/* __repr__ and __str__ */
/**
 * @brief
 *      return the string_value.
 *
 * @param[out] self - pointer to size_value structure
 *
 * @return      structure handle
 * @retval      pointer to size_value structure       	success
 * @retval      NULL					error
 *
 */

static PyObject *
pps_size_repr(PPSVR_Size_Object *self) {
	if (self->str_value) {
		return PyUnicode_FromString(self->str_value);
	} else {
		return PyUnicode_InternFromString("0");
	}
}



/* __cmp__ */
/**
 * @brief
 *	compares two size objects "self" and "with".
 *
 * @param[in] self - size object to compare
 * @param[in] with - size object to be compared with
 * @param[in] op - option for comparison
 *
 * @return	structure handle
 * @retval	Py_True			success
 * @retval	Py_False		error
 *
 */
static PyObject *
pps_size_richcompare(PPSVR_Size_Object *self, PyObject *with, int op)
{
	PyObject *result = Py_False; /* MUST incref result before return */
	struct attribute attr_self;
	struct attribute attr_with;
	int cmp_result;

	/* basic check make sure only size objects are compared */
	/* Al: I originally changed this to allow coercing compare operands but */
	/* ran into trouble with doing basic 'self' == "" as the empty string   */
	/* could not be converted into a size value. So I put back the original */
	/* assertion to only compare size values, but returning Py_False if the */
	/* size types don't match.  */
	if (!PyObject_TypeCheck(self, &PPSVR_Size_Type) ||
		!PyObject_TypeCheck(with, &PPSVR_Size_Type)) {
		Py_INCREF(result);
		return result;
	}

	COPY_SIZE_VALUE(attr_self.at_val.at_size, self->sz_value);
	COPY_SIZE_VALUE(attr_with.at_val.at_size, ((PPSVR_Size_Object *)with)->sz_value);

	cmp_result = comp_size(&attr_self, &attr_with);

	switch (op) {
		case Py_EQ:
			result = (cmp_result == 0) ? Py_True : Py_False;
			break;
		case Py_NE:
			result = (cmp_result != 0) ? Py_True : Py_False;
			break;
		case Py_LT:
			result = (cmp_result == -1) ? Py_True : Py_False;
			break;
		case Py_LE:
			result = (cmp_result <= 0) ? Py_True : Py_False;
			break;
		case Py_GT:
			result = (cmp_result == 1) ? Py_True : Py_False;
			break;
		case Py_GE:
			result = (cmp_result >= 0) ? Py_True : Py_False;
			break;
	}

	Py_INCREF(result);
	return result;

}

#undef COPY_SIZE_VALUE

/* add of two size object returns a NEW Refrence */

/* __add__ */
/**
 * @brief
 *	adds two python size objects and returns reference to it.
 *
 * @param[in] left - size object1
 * @param[in] right - size object2
 *
 * @return      structure handle
 * @retval      Py_True                 success
 * @retval      Py_False                error
 *
 */
static PyObject *
pps_size_number_methods_add(PyObject *left, PyObject *right)
{
	PyObject *result = Py_NotImplemented;
	struct size_value tmp_left;
	struct size_value tmp_right;
	struct size_value sz_result;
	u_Long	l_result;

	int rc;

	if ((PPSVR_Size_Type_Check(left)) && (PPSVR_Size_Type_Check(right))) {
		rc= normalize_size(&((PPSVR_Size_Object *)left)->sz_value,
			&((PPSVR_Size_Object *)right)->sz_value,
			&tmp_left,
			&tmp_right);

		if (rc != 0)
			goto QUIT;
		l_result = tmp_left.atsv_num + tmp_right.atsv_num;
		if ((l_result < tmp_left.atsv_num) || (l_result < tmp_right.atsv_num)) {
			PyErr_SetString(PyExc_ArithmeticError,
				"expression evaluates to wrong _size value (overflow?)");
			result = NULL;
			goto QUIT;
		}
		sz_result.atsv_num = l_result;
		sz_result.atsv_shift = tmp_left.atsv_shift;
		sz_result.atsv_units = tmp_left.atsv_units;
		result = PPSVR_Size_FromSizeValue(sz_result);
	}

QUIT:
	if ((result) && (result == Py_NotImplemented))
		Py_INCREF(result);
	return result;
}

/**
 * @brief
 *      subtracts two python size objects and returns reference to it.
 *
 * @param[in] left - size object1
 * @param[in] right - size object2
 *
 * @return      structure handle
 * @retval      Py_True                 success
 * @retval      Py_False                error
 *
 */

static PyObject *
pps_size_number_methods_subtract(PyObject *left, PyObject *right)
{
	PyObject *result = Py_NotImplemented;
	struct size_value tmp_left;
	struct size_value tmp_right;
	struct size_value sz_result;
	u_Long l_result;

	int rc;

	if ((PPSVR_Size_Type_Check(left)) && (PPSVR_Size_Type_Check(right))) {
		rc= normalize_size(&((PPSVR_Size_Object *)left)->sz_value,
			&((PPSVR_Size_Object *)right)->sz_value,
			&tmp_left,
			&tmp_right);

		if (rc != 0)
			goto QUIT;
		if (tmp_right.atsv_num > tmp_left.atsv_num) {
			PyErr_SetString(PyExc_ArithmeticError,
				"expression evaluates to negative _size value");
			result = NULL;
			goto QUIT;
		}
		l_result = tmp_left.atsv_num - tmp_right.atsv_num;
		sz_result.atsv_num = l_result;
		sz_result.atsv_shift = tmp_left.atsv_shift;
		sz_result.atsv_units = tmp_left.atsv_units;
		result = PPSVR_Size_FromSizeValue(sz_result);
	}

QUIT:
	if ((result) && (result == Py_NotImplemented))
		Py_INCREF(result);
	return result;
}

/**
 * @brief
 * 	Return the Python size's value in # oF kbytes.
 *
 * @param[in]	self - a Python size object
 *
 * @return long
 * @retval <n> # of bytes of the Python size object.
 * @retval 0	if there's an error
 *
 */
u_Long
pps_size_to_kbytes(PyObject *self)
{
	struct attribute attr;
	PPSVR_Size_Object *working_copy;
	if (!PPSVR_Size_Type_Check(self)) {
		return 0;
	}

	working_copy = (PPSVR_Size_Object *)self;

	if (working_copy == NULL)
		return 0;

	attr.at_flags = ATR_VFLAG_SET;
	attr.at_type = ATR_TYPE_SIZE;
	attr.at_val.at_size = working_copy->sz_value;

	return (get_kilobytes_from_attr(&attr));
}

/* --------- SIZE TYPE DEFINITION  --------- */


static PyNumberMethods pps_size_as_number = {
	/* nb_add */             (binaryfunc)pps_size_number_methods_add,
	/* nb_subtract */        (binaryfunc)pps_size_number_methods_subtract,
	/* nb_multiply */                   0,
	/* nb_remainder */                  0,
	/* nb_divmod */                     0,
	/* nb_power */                      0,
	/* nb_negative */                   0,
	/* nb_positive */        (unaryfunc)0,
	/* nb_absolute */        (unaryfunc)0,
	/* nb_bool */	           (inquiry)0,
	/* nb_invert */                     0,
	/* nb_lshift */                     0,
	/* nb_rshift */                     0,
	/* nb_and */                        0,
	/* nb_xor */                        0,
	/* nb_or */                         0,
	/* nb_int */                        0,
	/* nb_reserved */	            0,
	/* nb_float */                      0,
	/* nb_inplace_add */                0,
	/* nb_inplace_subtract */           0,
	/* nb_inplace_multiply */           0,
	/* nb_inplace_remainder */          0,
	/* nb_inplace_power */              0,
	/* nb_inplace_lshift */             0,
	/* nb_inplace_rshift */             0,
	/* nb_inplace_and */                0,
	/* nb_inplace_xor */                0,
	/* nb_inplace_or */                 0,
	/* nb_floor_divide */               0,
	/* nb_true_divide */                0,
	/* nb_inplace_floor_divide */       0,
	/* nb_inplace_true_divide */        0,
};

static char pps_size_doc[] =
    "_size()\n\
    \tPython representation of PBS internal size structure\n\
    ";

/* external, hopefully no clash */

PyTypeObject PPSVR_Size_Type = {
	PyVarObject_HEAD_INIT(NULL, 0)
	/* ob_size*/
	/* tp_name*/                        "_size",
	/* tp_basicsize*/                   sizeof(PPSVR_Size_Object),
	/* tp_itemsize*/                    0,
	/* tp_dealloc*/                     (destructor)pps_size_dealloc,
	/* tp_print*/                       0,
	/* tp_getattr*/                     0,
	/* tp_setattr*/                     0,
	/* tp_as_async */		    0,
	/* tp_repr*/                        (reprfunc)pps_size_repr,
	/* tp_as_number*/                   &pps_size_as_number,
	/* tp_as_sequence*/                 0,
	/* tp_as_mapping*/                  0,
	/* tp_hash */                       0,
	/* tp_call*/                        0,
	/* tp_str*/                         0,
	/* tp_getattro*/                    0,
	/* tp_setattro*/                    0,
	/* tp_as_buffer*/                   0,
	/* tp_flags*/                       Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,
	/* tp_doc */                        pps_size_doc,
	/* tp_traverse */                   0,
	/* tp_clear */                      0,
	/* tp_richcompare */                (richcmpfunc)pps_size_richcompare,
	/* tp_weaklistoffset */             0,
	/* tp_iter */                       0,
	/* tp_iternext */                   0,
	/* tp_methods */                    0,
	/* tp_members */                    0,
	/* tp_getset */                     0,
	/* tp_base */                       0,
	/* tp_dict */                       0,
	/* tp_descr_get */                  0,
	/* tp_descr_set */                  0,
	/* tp_dictoffset */                 0,
	/* tp_init */                       (initproc)pps_size_init,
	/* tp_alloc */                      0,
	/* tp_new */                        (newfunc)pps_size_new,
	/* tp_free */                       0,
	/* tp_is_gc For PyObject_IS_GC */   0,
	/* tp_bases */                      0,
	/* tp_mro */                        0,
	/* tp_cache */                      0,
	/* tp_subclasses */                 0,
	/* tp_weaklist */                   0
};


/* -----                  External Functions for size              ----- */

/**
 * @brief
 *	converts the input size_value struct to PyObject and returns reference to it.
 *
 * @param[in] from - size_value structure
 *
 * @return	structure handle
 * @retval	pointer to size PyObject	success
 * @retval	NULL				error
 *
 */
PyObject *
PPSVR_Size_FromSizeValue(struct size_value from)
{
	PPSVR_Size_Object *pyobj = NULL;

	if (!(pyobj = (PPSVR_Size_Object *)pps_size_new(&PPSVR_Size_Type, NULL, NULL)))
		goto ERROR_EXIT;
	pyobj->sz_value = from;
	if (_pps_size_make_str_value((PyObject *)pyobj) != 0)
		goto ERROR_EXIT;
	return (PyObject *)pyobj;
ERROR_EXIT:
	if (pyobj)
		Py_CLEAR(pyobj);
	return NULL;
}
