# -*- coding: utf-8 -*-

# ################################################################### #
#                                                                     #
#  BigBrotherBot(B3) (www.bigbrotherbot.net)                          #
#  Copyright (C) 2005 Michael "ThorN" Thornton                        #
#                                                                     #
#  This program is free software; you can redistribute it and/or      #
#  modify it under the terms of the GNU General Public License        #
#  as published by the Free Software Foundation; either version 2     #
#  of the License, or (at your option) any later version.             #
#                                                                     #
#  This program is distributed in the hope that it will be useful,    #
#  but WITHOUT ANY WARRANTY; without even the implied warranty of     #
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the       #
#  GNU General Public License for more details.                       #
#                                                                     #
#  You should have received a copy of the GNU General Public License  #
#  along with this program; if not, write to the Free Software        #
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA      #
#  02110-1301, USA.                                                   #
#                                                                     #
# ################################################################### #

__author__  = 'ThorN'
__version__ = '1.4.0'

import re

_PLACEHOLDER = re.compile(r'%(%|s)')


def escape_string(value):
    """
    Escape a value for use *inside* a single-quoted SQL string literal ('...').
    Single quotes are doubled (standard SQL, understood by MySQL, SQLite and PostgreSQL); backslashes are doubled
    as well when the active storage treats them as escape characters (MySQL).
    Prefer bind parameters (storage.query(sql, params) with %s placeholders): this is kept for old plugins.
    :param value: The value to escape (converted to str)
    """
    value = str(value)
    if QueryBuilder.backslash_escapes:
        value = value.replace('\\', '\\\\')
    return value.replace("'", "''")


def literal(value):
    """
    Return the given value as an SQL literal: numbers as-is, everything else as an escaped single-quoted string.
    """
    if isinstance(value, (int, float, complex)):
        return str(value)
    return "'%s'" % escape_string(value)


def _raw(fragment):
    """
    Return a hand-written SQL fragment ready to be joined to a statement that uses %s placeholders.
    """
    if isinstance(fragment, SQL):
        return fragment.text, fragment.params
    return str(fragment).replace('%', '%%'), ()


class SQL(str):
    """
    An SQL statement (or part of one) together with its bind parameters.

    `text` holds the statement with %s placeholders (a literal % is written %%) and `params` the values to bind:
    the storage layer executes the two separately, so values can never change the meaning of the query.
    The string value itself is the statement with the values inlined as escaped literals, which is what older
    code (and the logs) expect: existing plugins that concatenate or log queries keep working.
    """

    def __new__(cls, text, params=()):
        params = tuple(params)
        values = iter(params)
        inlined = _PLACEHOLDER.sub(lambda m: '%' if m.group(1) == '%' else literal(next(values)), text)
        obj = str.__new__(cls, inlined)
        obj.text = text
        obj.params = params
        return obj

    def __add__(self, other):
        if not isinstance(other, str):
            return NotImplemented
        text, params = _raw(other)
        return SQL(self.text + text, self.params + params)

    def __radd__(self, other):
        if not isinstance(other, str):
            return NotImplemented
        text, params = _raw(other)
        return SQL(text + self.text, params + self.params)

    def __reduce__(self):
        return SQL, (self.text, self.params)


def join(separator, parts):
    """
    Join SQL fragments (SQL objects or hand-written strings) keeping their bind parameters.
    """
    texts = []
    params = ()
    for part in parts:
        text, part_params = _raw(part)
        texts.append(text)
        params += part_params
    return SQL(_raw(separator)[0].join(texts), params)


class QueryBuilder(object):

    # Set by the storage layer on startup: MySQL treats backslashes inside string literals as escape characters,
    # SQLite and PostgreSQL (standard_conforming_strings) do not.
    backslash_escapes = False

    def __init__(self, db=None):
        """
        Object constructor.
        :param db: The current database connection.
        """
        self.db = db

    @staticmethod
    def _param(value):
        """
        Return the value to bind for the given value.
        None is stored as the string 'None', as B3 always did when it inlined values into its queries.
        """
        return 'None' if value is None else value

    def escape(self, word):
        """
        Return the given value as an SQL literal: numbers as-is, everything else as a properly escaped
        single-quoted string. Kept for old plugins: B3 itself binds values instead (see SQL).
        :param word: The value to escape
        """
        return literal(self._param(word))

    def quoteArgs(self, args):
        """
        Return a list of quoted arguments.
        :param args: The list of arguments to format.
        """
        if type(args[0]) is tuple or type(args[0]) is list:
            args = args[0]
        nargs = []
        for a in args:
            nargs.append(self.escape(a))
        return tuple(nargs)

    def fieldStr(self, fields):
        """
        Return a list of fields whose keywords are surrounded by backticks.
        :param fields: The list of fields to format.
        """
        if isinstance(fields, tuple) or isinstance(fields, list):
            return "`%s`" % "`, `".join(fields)
        elif isinstance(fields, str):
            if fields == "*":
                return fields
            else:
                return "`%s`" % fields
        else:
            raise TypeError('field must be a tuple, list, or string')

    def FieldClause(self, field, value=None):
        """
        Format a field clause in SQL according to the given parameters.
        :param field: The comparision type for this clause.
        :param value: The value of the comparision.
        :return: an SQL object (the value is a bind parameter)
        """
        field = field.strip()

        if type(value) == list or type(value) == tuple:
            return SQL("`" + field + "` IN(" + ",".join(['%s'] * len(value)) + ")",
                       [self._param(v) for v in value])

        value = '' if value is None else value

        if len(field) >= 2:
            for operator in ('>=', '<=', '<', '>', '='):
                if field.endswith(operator):
                    return SQL("`" + field[:-len(operator)].strip() + "` " + operator + " %s", [value])
            if field[-1] == "%" and field[0] == "%":
                return SQL("`" + field[1:-1].strip() + "` LIKE %s", ['%' + str(value) + '%'])
            elif field[-1] == "%":
                return SQL("`" + field[:-1].strip() + "` LIKE %s", [str(value) + '%'])
            elif field[0] == '%':
                return SQL("`" + field[1:].strip() + "` LIKE %s", ['%' + str(value)])
            elif field[0] == '&':
                return SQL("`" + field[1:].strip() + "` & %s", [value])
            elif field[0] == '|':
                return SQL("`" + field[1:].strip() + "` | %s", [value])

        return SQL("`" + field + "` = %s", [value])

    def WhereClause(self, fields=None, values=None, concat=' and '):
        """
        Construct a where clause for an SQL query.
        :param fields: The fields of the where clause.
        :param values: The value of each field.
        :param concat: The concat value for multiple where clauses
        :return: an SQL object, or `fields` itself when it is a hand-written clause
        """
        sql = []
        if isinstance(fields, tuple) and values is None \
                and len(fields) == 2:
            if isinstance(fields[1], list):
                values = tuple(fields[1])
            elif not isinstance(fields[1], tuple):
                values = (str(fields[1]),)

            if isinstance(fields[0], tuple) or isinstance(fields[0], list):
                fields = tuple(fields[0])
            elif not isinstance(fields[0], tuple):
                fields = (str(fields[0]),)
        else:
            if isinstance(fields, list):
                fields = tuple(fields)
            if isinstance(values, list):
                values = tuple(values)

        if isinstance(fields, tuple) and isinstance(values, tuple):
            # this will be a combination of both
            if len(fields) == 1 and len(values) == 1:
                sql.append(self.FieldClause(fields[0], values[0]))
            else:
                for k, field in enumerate(fields):
                    v = values[k]
                    sql.append(self.FieldClause(field, v))

        elif fields is not None and not isinstance(fields, tuple) \
                and values is not None and not isinstance(values, tuple):
            sql.append(self.FieldClause(fields, values))

        elif isinstance(fields, tuple) and len(fields) == 1 \
                and isinstance(values, str):
            sql.append(self.FieldClause(fields[0], values))

        elif isinstance(fields, tuple) and len(fields) > 0 \
                and isinstance(values, str):

            sql.append(self.FieldClause(fields[0], values))

            for field in fields[1:]:
                sql.append(self.FieldClause(field, ''))

        elif isinstance(fields, dict):
            for k, v in fields.items():
                sql.append(self.FieldClause(k, v))

        else:
            # its type is unknown, nothing we can do
            return fields

        return join(concat, sql)

    def SelectQuery(self, fields, table, where='', orderby='', limit=0, offset='', groupby='', having='', **keywords):
        """
        Construct a SQL select query.
        :param fields: A list of fields to select.
        :param table: The table from where to fetch data.
        :param where: A WHERE clause for this select statement.
        :param orderby: The ORDER BY clayse for this select statement.
        :param limit: The amount of data data to collect.
        :param offset: An offset which specifies how many records to skip.
        :param groupby: The GROUP BY clause for this select statement.
        :param having: The HAVING clause for this select statement.
        :param keywords: Unused at the moment.
        """
        sql = ['SELECT %s FROM `%s`' % (self.fieldStr(fields), table)]

        if where:
            sql.append(join('', ["WHERE ", self.WhereClause(where)]))
        if groupby:
            sql.append("GROUP BY %s" % groupby)
        if having:
            sql.append("HAVING %s" % having)
        if orderby:
            sql.append("ORDER BY %s" % orderby)
        if limit:
            sql.append("LIMIT")
        if offset:
            sql.append(offset + ",")
        if limit:
            sql.append(str(limit))

        return join(" ", sql)

    def UpdateQuery(self, data, table, where, delayed=None): 
        """
        Construct a SQL update query.
        :param data: A dictionary of key-value pairs for the update.
        :param table: The table from where to fetch data.
        :param where: A WHERE clause for this select statement.
        :param delayed: Whether to add the DELAYED clause to the query.
        """
        sql = "UPDATE "

        if delayed:
            sql += "DELAYED "

        sql += table + " SET "

        sets = [self.FieldClause(k, v) for k, v in data.items()]
        return join('', [sql, join(", ", sets), " WHERE ", self.WhereClause(where)])

    def InsertQuery(self, data, table, delayed=None): 
        """
        Construct a SQL insert query.
        :param data: A dictionary of key-value pairs for the update.
        :param table: The table from where to fetch data.
        :param delayed: Whether to add the DELAYED clause to the query.
        """
        sql = "INSERT "

        if delayed:
            sql += "DELAYED "

        sql += "INTO " + table

        keys = list(data.keys())
        sql = sql.replace('%', '%%') + "(" + self.fieldStr(keys) + ") VALUES (" + ", ".join(['%s'] * len(keys)) + ")"
        return SQL(sql, [self._param(data[k]) for k in keys])

    def ReplaceQuery(self, data, table, delayed=None): 
        """
        Construct a SQL replace query.
        :param data: A dictionary of key-value pairs for the update.
        :param table: The table from where to fetch data.
        :param delayed: Whether to add the DELAYED clause to the query.
        """
        sql = "REPLACE "

        if delayed:
            sql += "DELAYED "

        sql += "INTO " + table

        keys = list(data.keys())
        sql = sql.replace('%', '%%') + "(" + self.fieldStr(keys) + ") VALUES (" + ", ".join(['%s'] * len(keys)) + ")"
        return SQL(sql, [self._param(data[k]) for k in keys])
