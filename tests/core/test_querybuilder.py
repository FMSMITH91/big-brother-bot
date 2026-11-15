# -*- coding: utf-8 -*-

# ################################################################### #
#                                                                     #
#  BigBrotherBot(B3) (www.bigbrotherbot.net)                          #
#                                                                     #
#  This program is free software; you can redistribute it and/or      #
#  modify it under the terms of the GNU General Public License        #
#  as published by the Free Software Foundation; either version 2     #
#  of the License, or (at your option) any later version.             #
#                                                                     #
# ################################################################### #

import sqlite3
import unittest

from b3.querybuilder import QueryBuilder, escape_string


class Test_escaping(unittest.TestCase):

    def setUp(self):
        self._backslash_escapes = QueryBuilder.backslash_escapes
        QueryBuilder.backslash_escapes = False

    def tearDown(self):
        QueryBuilder.backslash_escapes = self._backslash_escapes

    def test_literals(self):
        qb = QueryBuilder()
        self.assertEqual("5", qb.escape(5))
        self.assertEqual("1.5", qb.escape(1.5))
        self.assertEqual("'None'", qb.escape(None))
        self.assertEqual("'O''Neil'", qb.escape("O'Neil"))
        self.assertEqual("'say \"hi\"'", qb.escape('say "hi"'))

    def test_backslashes_doubled_only_for_mysql(self):
        self.assertEqual("a\\b", escape_string("a\\b"))
        QueryBuilder.backslash_escapes = True
        self.assertEqual("a\\\\b''c", escape_string("a\\b'c"))

    def test_player_name_cannot_inject_sql_on_sqlite(self):
        db = sqlite3.connect(':memory:')
        db.execute("CREATE TABLE clients (name TEXT)")
        db.executemany("INSERT INTO clients VALUES (?)", [('Joe',), ('Ann',)])
        for evil in ('" OR 1=1 --', "' OR 1=1 --", 'x\\', "a'b\"c\\"):
            query = QueryBuilder(db).SelectQuery('*', 'clients', {'name': evil})
            self.assertEqual([], db.execute(query).fetchall(), query)
        # and the value round-trips unchanged
        name = "O'Neil \"the\" \\ hacker"
        db.execute(QueryBuilder(db).InsertQuery({'name': name}, 'clients'))
        found = db.execute(QueryBuilder(db).SelectQuery('*', 'clients', {'name': name})).fetchall()
        self.assertEqual([(name,)], found)

    def test_like_clause_with_quote(self):
        db = sqlite3.connect(':memory:')
        db.execute("CREATE TABLE clients (name TEXT)")
        db.execute("INSERT INTO clients VALUES ('O''Neil')")
        query = QueryBuilder(db).SelectQuery('*', 'clients', {'%name%': "'Ne"})
        self.assertEqual([("O'Neil",)], db.execute(query).fetchall(), query)


class Test_FieldClause(unittest.TestCase):

    def test_comparison_operators(self):
        qb = QueryBuilder()
        self.assertEqual("`time_add` >= 5", qb.FieldClause('time_add >=', 5))
        self.assertEqual("`time_add` <= 5", qb.FieldClause('time_add <=', 5))
        self.assertEqual("`time_add` > 5", qb.FieldClause('time_add >', 5))
        self.assertEqual("`time_add` < 5", qb.FieldClause('time_add <', 5))
        self.assertEqual("`time_add` = 5", qb.FieldClause('time_add', 5))


class Test_SelectQuery(unittest.TestCase):

    def test_group_by_uses_groupby(self):
        qb = QueryBuilder()
        query = qb.SelectQuery('*', 'clients', groupby='`group_bits`', orderby='`id` DESC')
        self.assertIn('GROUP BY `group_bits`', query)
        self.assertIn('ORDER BY `id` DESC', query)
        self.assertLess(query.index('GROUP BY'), query.index('ORDER BY'))


class Test_WhereClause(unittest.TestCase):

    def test_no_stray_output(self):
        import io
        from contextlib import redirect_stdout
        qb = QueryBuilder()
        buf = io.StringIO()
        with redirect_stdout(buf):
            clause = qb.WhereClause(('id', 'name'), (5, 'foo'))
        self.assertEqual("`id` = 5 and `name` = 'foo'", clause)
        self.assertEqual('', buf.getvalue())


class Test_bind_parameters(unittest.TestCase):

    def setUp(self):
        self._backslash_escapes = QueryBuilder.backslash_escapes
        QueryBuilder.backslash_escapes = False

    def tearDown(self):
        QueryBuilder.backslash_escapes = self._backslash_escapes

    def test_values_are_kept_out_of_the_sql_text(self):
        evil = "' OR 1=1 --"
        query = QueryBuilder().SelectQuery('*', 'clients', {'name': evil}, 'id', 1)
        self.assertEqual("SELECT * FROM `clients` WHERE `name` = %s ORDER BY id LIMIT 1", query.text)
        self.assertEqual((evil,), query.params)
        # the string value is still the old, escaped form for code that logs or concatenates queries
        self.assertEqual("SELECT * FROM `clients` WHERE `name` = ''' OR 1=1 --' ORDER BY id LIMIT 1", str(query))

    def test_insert_update_and_like(self):
        qb = QueryBuilder()
        insert = qb.InsertQuery({'name': "O'Neil", 'connections': 3, 'greeting': None}, 'clients')
        self.assertEqual("INSERT INTO clients(`name`, `connections`, `greeting`) VALUES (%s, %s, %s)", insert.text)
        self.assertEqual(("O'Neil", 3, 'None'), insert.params)
        update = qb.UpdateQuery({'name': 'x'}, 'clients', {'id': 5})
        self.assertEqual("UPDATE clients SET `name` = %s WHERE `id` = %s", update.text)
        self.assertEqual(('x', 5), update.params)
        like = qb.FieldClause('%name%', 'joe')
        self.assertEqual(("`name` LIKE %s", ('%joe%',)), (like.text, like.params))
        in_clause = qb.FieldClause('id', [1, 2])
        self.assertEqual(("`id` IN(%s,%s)", (1, 2)), (in_clause.text, in_clause.params))

    def test_concatenation_keeps_parameters(self):
        where = QueryBuilder().WhereClause({'type': 'Ban'})
        where += ' AND time_expire > 100'
        query = "SELECT COUNT(id) total FROM penalties WHERE " + where
        self.assertEqual("SELECT COUNT(id) total FROM penalties WHERE `type` = %s AND time_expire > 100", query.text)
        self.assertEqual(('Ban',), query.params)

    def test_literal_percent_in_hand_written_fragments(self):
        query = QueryBuilder().SelectQuery('*', 'clients', {'name': 'joe'}, "FIELD(name, '50%')")
        self.assertIn("'50%%'", query.text)
        self.assertIn("'50%'", str(query))

    def test_sqlite_executes_bound_query(self):
        db = sqlite3.connect(':memory:')
        db.execute("CREATE TABLE clients (name TEXT)")
        db.execute("INSERT INTO clients VALUES ('joe')")
        query = QueryBuilder(db).SelectQuery('*', 'clients', {'name': "joe' OR '1'='1"})
        self.assertEqual([], db.execute(query.text.replace('%s', '?'), query.params).fetchall())

if __name__ == '__main__':
    unittest.main()
