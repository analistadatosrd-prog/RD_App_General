import streamlit as st
import psycopg2
import psycopg2.extras


def get_conn():
    return psycopg2.connect(st.secrets["DATABASE_URL"])


def fetch_all(query, params=None):
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, params or ())
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def fetch_one(query, params=None):
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, params or ())
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        conn.close()


def execute(query, params=None):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(query, params or ())
        conn.commit()
    finally:
        conn.close()
