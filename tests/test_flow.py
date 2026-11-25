import os
import re
import tempfile
import unittest
from pathlib import Path

from werkzeug.datastructures import MultiDict

from venna import create_app
from venna.models import Lead, Quote, Revision


class CRMFlow(unittest.TestCase):
    password = "venna-teste-longo-123"

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.app = create_app({
            "TESTING": True,
            "SECRET_KEY": "chave-apenas-para-teste-por-trinta-e-dois",
            "SESSION_COOKIE_SECURE": False,
            "DATABASE_URL": f"sqlite:///{self.temp.name}/crm.db",
        })
        os.environ["VENNA_BASE_URL"] = "http://127.0.0.1:8000"
        self.cli("init-db")
        self.one = self.app.test_client()
        self.two = self.app.test_client()
        self.guest = self.app.test_client()

    def cli(self, *args):
        result = self.app.test_cli_runner().invoke(args=args)
        self.assertEqual(result.exit_code, 0, result.output)
        return result.output

    def post(self, client, url, source, data):
        response = client.get(source)
        token = re.search(rb'name="csrf_token" value="([^"]+)"', response.data)
        self.assertIsNotNone(token, f"{source}: HTTP {response.status_code}")
        values = MultiDict(data)
        values.add("csrf_token", token[1].decode())
        return client.post(url, data=values)

    def account(self, client, email, name):
        token = self.cli("invite", "--email", email, "--name", name).split("#convite=")[1].strip()
        passwords = {"token": token, "password": self.password, "confirmation": self.password}
        self.assertEqual(self.post(client, "/ativar", "/ativar", passwords).status_code, 302)
        self.assertEqual(self.post(client, "/ativar", "/ativar", passwords).status_code, 400)
        self.assertEqual(self.post(client, "/login", "/login",
                                  {"email": email, "password": self.password}).status_code, 302)

    def test_private_workflow_and_versioned_pdf(self):
        self.assertEqual(self.guest.get("/").location, "/login")
        self.assertEqual(self.guest.get("/simulador").location, "/login")
        self.assertEqual(self.guest.get("/orcamentos/1/v/1/pdf").location, "/login")
        self.assertEqual(self.guest.post("/login").status_code, 400)
        self.account(self.one, "comercial@example.test", "Equipe VENNA")
        self.account(self.two, "socia@example.test", "Segunda conta de teste")
        self.assertIn(b"Carteira de leads", self.one.get("/").data)

        lead_data = {"name": "Estúdio Horizonte (exemplo)", "source": "Indicação", "stage": "new",
                     "city": "Salvador/BA", "phone": "(00) 00000-0000", "assignee_id": "2",
                     "followup": "2026-11-03", "notes": "NOTA INTERNA DE TESTE"}
        lead = self.post(self.one, "/leads/novo", "/leads/novo", lead_data)
        self.assertEqual(lead.status_code, 302)
        self.assertIn(b"Horizonte", self.two.get(lead.location).data)
        self.assertIn(b"Segunda conta de teste", self.two.get(lead.location).data)
        self.assertIn(b"Horizonte", self.one.get("/?retornos=1").data)

        quote_data = MultiDict([
            ("lead_id", "1"), ("description", "Mármore Bege Bahia levigado"), ("unit", "m²"),
            ("quantity", "153"), ("rate", "175,00"),
            ("description", "Amostra para aprovação"), ("unit", "un"),
            ("quantity", "1"), ("rate", "35,50"),
            ("freight", "280,00"), ("delivery", "Prazo a combinar após a confirmação do pedido."),
            ("payment", "Condições de pagamento a combinar."),
            ("unloading", "Descarregamento conforme condições acordadas para a entrega."),
            ("remarks", "Cotação demonstrativa com dados fictícios."),
        ])
        result = self.post(self.one, "/simulador", "/simulador", quote_data)
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result.location, "/orcamentos/1")
        self.assertIn(b"R$ 27.090,50", self.two.get("/orcamentos/1").data)

        pdf_url = "/orcamentos/1/v/1/pdf"
        pdf = self.one.get(pdf_url)
        self.assertEqual(pdf.mimetype, "application/pdf")
        self.assertTrue(pdf.data.startswith(b"%PDF"))
        self.assertEqual(pdf.headers["Cache-Control"], "no-store")
        if sample := os.environ.get("VENNA_QA_SAMPLE"):
            Path(sample).write_bytes(pdf.data)

        update = {"revision": "1", "old_status": "draft", "status": "sent"}
        self.assertEqual(self.post(self.two, "/orcamentos/1/status", "/orcamentos/1", update).status_code, 302)
        self.assertEqual(self.post(self.one, "/orcamentos/1/status", "/orcamentos/1", update).status_code, 409)
        self.assertIn(b"Enviado", self.one.get("/orcamentos?status=sent").data)
        with self.app.extensions["venna_db"]() as db:
            self.assertEqual(db.get(Lead, 1).stage, "quoted")
            self.assertEqual(db.get(Revision, (1, 1)).data["total"], 2_709_050)

        quote_data["revision"], quote_data["old_status"], quote_data["freight"] = "1", "sent", ""
        quote_data.setlist("quantity", ["0,125", "1"])
        quote_data.setlist("rate", ["1,00", "35,50"])
        revision_url = "/orcamentos/1/revisar"
        self.assertEqual(self.post(self.two, revision_url, revision_url, quote_data).status_code, 302)
        self.assertEqual(self.post(self.one, revision_url, revision_url, quote_data).status_code, 409)
        page = self.one.get("/orcamentos/1").data
        self.assertIn(b"R$ 35,63", page)
        self.assertIn(b"Total sem frete", page)
        self.assertTrue(self.one.get(pdf_url).data.startswith(b"%PDF"))
        with self.app.extensions["venna_db"]() as db:
            self.assertEqual(db.get(Quote, 1).revision, 2)
            self.assertEqual(db.get(Revision, (1, 1)).data["total"], 2_709_050)
            self.assertEqual(db.get(Revision, (1, 2)).data["total"], 3563)

        self.cli("disable-account", "socia@example.test")
        self.assertEqual(self.two.get(pdf_url).location, "/login")
        self.assertEqual(self.one.get(pdf_url).status_code, 200)

    def test_invalid_amounts_do_not_save(self):
        self.account(self.one, "comercial@example.test", "Equipe VENNA")
        self.post(self.one, "/leads/novo", "/leads/novo", {
            "name": "Lead de teste", "stage": "new", "source": "Site",
        })
        url = "/leads/1/orcamentos/novo"
        data = {"description": "Pedra", "unit": "m²", "quantity": "10,25", "rate": "123,45"}
        for invalid in ("-1", "1,003", "1e2", "um"):
            with self.subTest(invalid=invalid):
                self.assertEqual(self.post(self.one, url, url, dict(data, freight=invalid)).status_code, 422)
        self.assertEqual(self.one.get("/orcamentos/1").status_code, 404)


if __name__ == "__main__":
    unittest.main()
