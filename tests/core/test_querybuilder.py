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


if __name__ == '__main__':
    unittest.main()
