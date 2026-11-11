"""Teste de fumaça: nenhum servidor pré-cadastrado; login e cadastro por papéis."""
import os
import tempfile
import unittest

_temp = tempfile.TemporaryDirectory()
os.environ["DATA_DIR"] = _temp.name
os.environ["PADRE_USER"] = "padre_teste"
os.environ["PADRE_PASSWORD"] = "senha-forte-de-teste-123"
os.environ["SECRET_KEY"] = "chave-muito-forte-exclusiva-de-teste-123456789"
os.environ.pop("DATABASE_URL", None)
os.environ.pop("PRODUCAO", None)

from app import app
import database

class AplicacaoTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def _post(self, path, data):
        with self.client.session_transaction() as s:
            token = s.get("csrf")
        return self.client.post(path, data={"csrf_token": token, **data}, follow_redirects=True)

    def test_pagina_publica_e_saude(self):
        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertEqual(self.client.get("/saude").data, b"ok")
        self.assertNotIn(b"Quiz", self.client.get("/").data)

    def test_fluxo_padre_coordenador_servidor(self):
        self.assertEqual(self.client.get("/usuarios").status_code, 302)
        self.client.get("/entrar")
        resp = self._post("/entrar", {"usuario":"padre_teste","senha":"senha-forte-de-teste-123"})
        self.assertEqual(resp.status_code, 200)
        resp = self._post("/usuarios", {"nome":"Coordenador Exemplo","usuario":"coord_demo","senha":"senha-coordenador-123"})
        self.assertEqual(resp.status_code, 200)
        with app.app_context():
            c = database.conectar()
            self.assertEqual(c.execute("SELECT COUNT(*) AS n FROM usuarios WHERE perfil='servidor'").fetchone()["n"], 0)
            c.close()
        self._post("/sair", {})
        self.client.get("/entrar")
        self._post("/entrar", {"usuario":"coord_demo","senha":"senha-coordenador-123"})
        resp = self._post("/usuarios", {"nome":"Servidor Exemplo","usuario":"serv_demo","senha":"senha-servidor-123"})
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Servidor Exemplo", resp.data)
        with app.app_context():
            c = database.conectar()
            servidor_id = c.execute("SELECT id FROM usuarios WHERE usuario='serv_demo'").fetchone()["id"]
            c.close()
        resp = self._post("/missas/nova", {
            "nome":"Missa de teste", "data":"2099-05-20","hora":"18:00",
            "quantidade":"1","disponiveis":str(servidor_id),"recado":"Chegar cedo"
        })
        self.assertEqual(resp.status_code, 200)
        with app.app_context():
            c = database.conectar()
            self.assertEqual(c.execute("SELECT COUNT(*) AS n FROM missas").fetchone()["n"], 1)
            self.assertEqual(c.execute("SELECT COUNT(*) AS n FROM escala").fetchone()["n"], 1)
            c.close()

if __name__ == "__main__":
    unittest.main()
