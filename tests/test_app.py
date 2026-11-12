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
        resp = self._post("/usuarios", {"nome":"Servidor Exemplo"})
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Servidor Exemplo", resp.data)
        self.assertNotIn(b"@servidor_", resp.data)
        with app.app_context():
            c = database.conectar()
            servidor_id = c.execute("SELECT id FROM usuarios WHERE perfil='servidor' AND nome='Servidor Exemplo'").fetchone()["id"]
            c.close()
        resp = self._post("/missas/nova", {
            "nome":"Missa de teste", "data":"2099-05-20","hora":"18:00",
            "quantidade":"1","disponiveis":str(servidor_id),"funcoes":"Missal","recado":"Chegar cedo"
        })
        self.assertEqual(resp.status_code, 200)
        with app.app_context():
            c = database.conectar()
            self.assertEqual(c.execute("SELECT COUNT(*) AS n FROM missas").fetchone()["n"], 1)
            self.assertEqual(c.execute("SELECT COUNT(*) AS n FROM escala").fetchone()["n"], 1)
            c.close()
        self._post("/sair", {})
        self.client.get("/entrar")
        self._post("/entrar", {"usuario":"padre_teste","senha":"senha-forte-de-teste-123"})
        self._post("/usuarios", {"nome":"Coordenador Leitores","usuario":"coord_leitor","senha":"senha-leitores-123","grupo":"leitor"})
        self._post("/sair", {})
        self.client.get("/entrar")
        self._post("/entrar", {"usuario":"coord_leitor","senha":"senha-leitores-123"})
        self.assertEqual(self.client.get("/missas/1/editar").status_code, 404)
        self.assertNotIn(b"Servidor Exemplo", self.client.get("/usuarios").data)

    def test_separacao_das_equipes_de_servidores(self):
        self.client.get("/entrar")
        self._post("/entrar", {"usuario": "padre_teste", "senha": "senha-forte-de-teste-123"})
        resposta = self._post("/usuarios", {
            "nome": "Coordenação de Acólitos", "usuario": "coord_acolitos",
            "senha": "senha-acolitos-123", "grupo": "acolitos",
        })
        self.assertIn("Coordenação de Acólitos", resposta.get_data(as_text=True))

        self._post("/sair", {})
        self.client.get("/entrar")
        self._post("/entrar", {"usuario": "coord_acolitos", "senha": "senha-acolitos-123"})
        resposta = self._post("/usuarios", {"nome": "Servidor dos Acólitos"})
        self.assertIn("Servidor dos Acólitos", resposta.get_data(as_text=True))
        db = database.conectar()
        try:
            servidor = db.execute("SELECT id,grupo FROM usuarios WHERE nome=?", ("Servidor dos Acólitos",)).fetchone()
            self.assertEqual(servidor["grupo"], "acolitos")
        finally:
            db.close()

        self._post("/missas/nova?grupo=leitor", {
            "nome": "Missa dos Acólitos", "data": "2099-06-01", "hora": "10:00",
            "quantidade": "1", "disponiveis": str(servidor["id"]), "funcoes": "Missal",
        })
        db = database.conectar()
        try:
            missa = db.execute("SELECT id,grupo FROM missas WHERE nome=?", ("Missa dos Acólitos",)).fetchone()
            self.assertEqual(missa["grupo"], "acolitos")
        finally:
            db.close()
        self.assertNotIn("Missa dos Acólitos", self.client.get("/?grupo=acolitos").get_data(as_text=True))
        self._post(f"/missas/{missa['id']}/publicacao", {})
        self._post("/avisos/novo", {"titulo": "Ensaio dos Acólitos", "mensagem": "Trazer o missal."})
        self._post("/sair", {})

        pagina = self.client.get("/?grupo=acolitos").get_data(as_text=True)
        self.assertIn("Missa dos Acólitos", pagina)
        self.assertIn("Ensaio dos Acólitos", pagina)
        for grupo in ("coroinhas", "cerimoniarios", "altar", "leitor"):
            pagina = self.client.get(f"/?grupo={grupo}").get_data(as_text=True)
            self.assertNotIn("Missa dos Acólitos", pagina)
            self.assertNotIn("Ensaio dos Acólitos", pagina)

if __name__ == "__main__":
    unittest.main()
