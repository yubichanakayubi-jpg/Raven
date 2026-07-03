import os
import unittest
from types import SimpleNamespace

os.environ.setdefault("DISCORD_TOKEN", "teste")
os.environ.setdefault("GEMINI_API_KEY", "teste")
os.environ.setdefault("GROQ_API_KEY", "teste")

import data.runtime as runtime
import events


class FakeGuild:
    def __init__(self, guild_id):
        self.id = guild_id

    def get_member(self, _member_id):
        return None


class FakeChannel:
    def __init__(self, channel_id, guild):
        self.id = channel_id
        self.guild = guild
        self.name = "chat-geral"
        self.category = None


class FakeAuthor:
    def __init__(self, user_id, display_name, *, bot=False):
        self.id = user_id
        self.display_name = display_name
        self.name = display_name
        self.bot = bot


class FakeMessage:
    def __init__(
        self,
        *,
        message_id,
        content,
        author,
        channel,
        guild,
        client_user_id=999,
        reference=None,
    ):
        self.id = message_id
        self.content = content
        self.clean_content = content
        self.author = author
        self.channel = channel
        self.guild = guild
        self.reference = reference
        self.client = SimpleNamespace(user=SimpleNamespace(id=client_user_id))
        self.mentions = []


class RavenContextTests(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        runtime.raven_conversas.clear()
        runtime.raven_conversas_por_usuario.clear()
        runtime.raven_sessoes_por_mensagem.clear()

        self.guild = FakeGuild(1)
        self.channel = FakeChannel(10, self.guild)
        self.raven_author = FakeAuthor(999, "Raven", bot=True)
        self.miss = FakeAuthor(100, "MissMoon")
        self.cowboy = FakeAuthor(200, "Cowboy")

    def _registrar_usuario(self, sessao, message):
        events.registrar_mensagem_usuario_conversa_raven(
            sessao,
            message,
            events.conteudo_mensagem_para_contexto_ia(message, 260),
        )

    def _registrar_bot(self, sessao, content, origem, message_id):
        bot_message = FakeMessage(
            message_id=message_id,
            content=content,
            author=self.raven_author,
            channel=self.channel,
            guild=self.guild,
        )
        events.registrar_resposta_conversa_raven(sessao, bot_message, origem, content)
        return bot_message

    def test_caso_1_mencao_nao_puxa_assunto_solto_do_canal(self):
        agora = 1000.0
        cowboy_filme = FakeMessage(
            message_id=1,
            content="Qual nome voce daria para esse filme?",
            author=self.cowboy,
            channel=self.channel,
            guild=self.guild,
        )
        direcionada, motivo, sessao = events.resolver_direcionamento_raven(
            cowboy_filme,
            bot_foi_mencionado=False,
            respondeu_bot=False,
            mensagem_respondida=None,
            agora_ts=agora,
        )
        self.assertFalse(direcionada)
        self.assertIsNone(sessao)
        self.assertEqual(motivo, "ignorada")

        miss_mencao = FakeMessage(
            message_id=2,
            content="@Raven raven o Cowboy te chamou de desonesto",
            author=self.miss,
            channel=self.channel,
            guild=self.guild,
        )
        direcionada, motivo, sessao = events.resolver_direcionamento_raven(
            miss_mencao,
            bot_foi_mencionado=True,
            respondeu_bot=False,
            mensagem_respondida=None,
            agora_ts=agora + 1,
        )
        self.assertTrue(direcionada)
        self.assertEqual(motivo, "mention")
        self._registrar_usuario(sessao, miss_mencao)
        contexto = events.montar_contexto_estruturado_raven(
            miss_mencao,
            sessao=sessao,
            motivo_direcao="mention",
        )
        self.assertNotIn("filme", contexto.casefold())

    def test_caso_2_followup_entende_vc_como_raven_sem_trocar_autor(self):
        agora = 2000.0
        miss_mencao = FakeMessage(
            message_id=10,
            content="@Raven raven o Cowboy te chamou de desonesto",
            author=self.miss,
            channel=self.channel,
            guild=self.guild,
        )
        _, _, sessao = events.resolver_direcionamento_raven(
            miss_mencao,
            bot_foi_mencionado=True,
            respondeu_bot=False,
            mensagem_respondida=None,
            agora_ts=agora,
        )
        self._registrar_usuario(sessao, miss_mencao)
        self._registrar_bot(sessao, "O Cowboy vai ter que se explicar.", miss_mencao, 11)

        miss_followup = FakeMessage(
            message_id=12,
            content="Falou que vc estava estragado e que era desonesto",
            author=self.miss,
            channel=self.channel,
            guild=self.guild,
        )
        direcionada, motivo, sessao_followup = events.resolver_direcionamento_raven(
            miss_followup,
            bot_foi_mencionado=False,
            respondeu_bot=False,
            mensagem_respondida=None,
            agora_ts=agora + 5,
        )
        self.assertTrue(direcionada)
        self.assertEqual(motivo, "followup")
        self.assertEqual(sessao["session_id"], sessao_followup["session_id"])
        self._registrar_usuario(sessao_followup, miss_followup)

        contexto = events.montar_contexto_estruturado_raven(
            miss_followup,
            sessao=sessao_followup,
            motivo_direcao="followup",
        )
        self.assertIn("'voce/vc/tu/ce' normalmente se refere ao Raven", contexto)
        self.assertIn("Cowboy", contexto)

    def test_caso_3_nova_mencao_resetando_assunto_sem_filme(self):
        agora = 3000.0
        miss_filme = FakeMessage(
            message_id=20,
            content="Esse filme e muito bom",
            author=self.miss,
            channel=self.channel,
            guild=self.guild,
        )
        direcionada, _, _ = events.resolver_direcionamento_raven(
            miss_filme,
            bot_foi_mencionado=False,
            respondeu_bot=False,
            mensagem_respondida=None,
            agora_ts=agora,
        )
        self.assertFalse(direcionada)

        miss_idade = FakeMessage(
            message_id=21,
            content="@Raven voce tem quantos anos?",
            author=self.miss,
            channel=self.channel,
            guild=self.guild,
        )
        _, _, sessao = events.resolver_direcionamento_raven(
            miss_idade,
            bot_foi_mencionado=True,
            respondeu_bot=False,
            mensagem_respondida=None,
            agora_ts=agora + 2,
        )
        self._registrar_usuario(sessao, miss_idade)
        contexto = events.montar_contexto_estruturado_raven(
            miss_idade,
            sessao=sessao,
            motivo_direcao="mention",
        )
        self.assertIn("quantos anos", contexto.casefold())
        self.assertNotIn("filme", contexto.casefold())
        invalida = events.garantir_resposta_no_contexto_raven(
            "Esse filme parece bom demais.",
            sessao,
            message=miss_idade,
        )
        self.assertEqual(invalida, events.RAVEN_RESPOSTA_FORA_CONTEXTO)

    def test_caso_4_reply_usa_sessao_da_mensagem_especifica_do_raven(self):
        agora = 4000.0
        miss_idade = FakeMessage(
            message_id=30,
            content="@Raven voce tem quantos anos?",
            author=self.miss,
            channel=self.channel,
            guild=self.guild,
        )
        _, _, sessao = events.resolver_direcionamento_raven(
            miss_idade,
            bot_foi_mencionado=True,
            respondeu_bot=False,
            mensagem_respondida=None,
            agora_ts=agora,
        )
        self._registrar_usuario(sessao, miss_idade)
        bot_msg = self._registrar_bot(sessao, "Sou antigo como a noite da FDN.", miss_idade, 31)

        reply = FakeMessage(
            message_id=32,
            content="Isso e bom ou ruim?",
            author=self.miss,
            channel=self.channel,
            guild=self.guild,
            reference=SimpleNamespace(message_id=bot_msg.id),
        )
        direcionada, motivo, sessao_reply = events.resolver_direcionamento_raven(
            reply,
            bot_foi_mencionado=False,
            respondeu_bot=True,
            mensagem_respondida=bot_msg,
            agora_ts=agora + 5,
        )
        self.assertTrue(direcionada)
        self.assertEqual(motivo, "reply")
        self.assertEqual(sessao["session_id"], sessao_reply["session_id"])
        self._registrar_usuario(sessao_reply, reply)

        contexto = events.montar_contexto_estruturado_raven(
            reply,
            sessao=sessao_reply,
            motivo_direcao="reply",
            mensagem_respondida=bot_msg,
        )
        self.assertIn("MENSAGEM_DO_RAVEN_REFERENCIADA", contexto)
        self.assertIn("Sou antigo como a noite da FDN", contexto)
        self.assertIn("Isso e bom ou ruim?", contexto)


if __name__ == "__main__":
    unittest.main()
