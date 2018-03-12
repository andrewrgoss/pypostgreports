#!/usr/bin/env python

import report, sys

import psycopg2.extras

parser = report.get_parser(sys.argv[0])
parser.add_argument('--title', '-t', required=False, dest='title', default="Data Dictionary", help='Report Title')

args = parser.parse_args()
conn = report.get_connection(args)
curs = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

def get_dictionary():
    q = """
    select t1.nspname as schema, count(*) as count
    from pg_namespace t1
    join information_schema.tables t2 on t1.nspname = t2.table_schema
    left outer join pg_description t3 on t1.oid = t3.objoid
    where t1.nspname not in ('information_schema', 'pg_catalog')
    group by schema, description
    order by schema
    """

    curs.execute(q)

    schemas = curs.fetchall()

    for schema in schemas:
        schema_name = schema['schema']

        q = """
        select table_name as table
        from information_schema.tables t1
        join pg_class t2 on (table_name = relname)
        left outer join pg_description t3 on (t2.oid = objoid and objsubid = 0)
        where table_schema = '{schema_name}'
        order by table_name
        """.format(**vars())

        curs.execute(q)

        tables = curs.fetchall()

        for table in tables:
            table_name = table['table']

            q = """
            with samples as (
              select table_schema, 
                     table_name, 
                     query_to_xml(format('select * from %I.%I limit 1', table_schema, table_name), true, true, '') 
                     as sample_row
              from information_schema.tables 
              where table_schema = '{schema_name}'
            )
            select c.column_name as column, c.data_type,
                case when s.sample_row is document 
                    then (xpath('/row/'||column_name||'/text()', s.sample_row))[1]::text 
                else null end as sample_value
            from information_schema.columns c 
              join samples s on (s.table_schema, s.table_name) = (c.table_schema, c.table_name)
            where c.table_name = '{table_name}'
            order by ordinal_position
            """.format(**vars())

            curs.execute(q)

            table['columns'] = curs.fetchall()

        schema['tables'] = tables

    return schemas

tmpl_vars = {
    'dictionary': get_dictionary(),
    'title': args.title
}

report.generate_report(tmpl_vars, args)