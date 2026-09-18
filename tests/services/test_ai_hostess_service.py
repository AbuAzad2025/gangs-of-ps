import json
from datetime import datetime, timedelta, timezone

from flask import session
from models.hostess import Hostess, HostessChatMessage, HostessMemory
from models.knowledge import HostessKnowledge
from services.ai_hostess_service import AIHostessService
from flask import session


def _hostess(db, **kwargs):
    item = Hostess(
        name=kwargs.pop("name", "Jasmin"),
        role=kwargs.pop("role", "greeter"),
        dialogue_style="friendly",
        **kwargs,
    )
    db.session.add(item)
    db.session.flush()
    return item


def test_prompt_contains_context_role_pack_and_dynamic_sections(app):
    service = AIHostessService()
    with app.app_context():
        prompt = service._build_system_prompt(
            {"name": "Ruby", "role": "support", "description": "calm guide",
             "dialogue_style": "warm"},
            {"name": "Player", "money": 10, "level": 60, "health": 20,
             "is_in_jail": True, "last_battle_result": "won"},
            dynamic_knowledge="\nFAQ answer",
            language="en",
            memory_text="- likes: racing",
            tone="formal",
        )
    assert "You are Ruby" in prompt
    assert "Core duties" in prompt
    assert "FAQ answer" in prompt and "likes: racing" in prompt
    assert "JAIL" in prompt and "JUST WON" in prompt
    assert "formal" in prompt.lower()


def test_openai_request_sanitizes_history_and_training_examples(app, monkeypatch):
    service = AIHostessService()
    captured = {}

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": "answer"}}]}

    def post(url, **kwargs):
        captured.update(kwargs)
        return Response()

    monkeypatch.setattr("services.ai_hostess_service.requests.post", post)
    with app.app_context():
        result = service._call_openai(
            "secret", "What is the gym?",
            {"id": 1, "name": "Jasmin", "role": "greeter",
             "training_examples": json.dumps([
                 {"role": "user", "content": "example"},
                 {"role": "system", "content": "must be ignored"},
             ])},
            {"id": 2, "language": "en"},
            [{"role": "system", "content": "attack"},
             {"role": "user", "content": "old question"},
             {"role": "assistant", "content": "old answer"},
             {"role": "developer", "content": "ignored"}],
        )
    messages = captured["json"]["messages"]
    assert result == "answer"
    assert all(m["role"] in ("system", "user", "assistant") for m in messages)
    assert not any(m["content"] == "attack" for m in messages)
    assert any(m["content"] == "example" for m in messages)
    assert messages[-1] == {"role": "user", "content": "What is the gym?"}


def test_rag_retrieval_filters_language_and_hostess(app, db):
    service = AIHostessService()
    with app.app_context():
        hostess = _hostess(db)
        db.session.add_all([
            HostessKnowledge(question="How do I train?", answer="Visit the gym",
                             keywords="gym training", language="en"),
            HostessKnowledge(question="How do I train?", answer="wrong language",
                             keywords="gym training", language="ar"),
            HostessKnowledge(hostess_id=hostess.id, question="How do I train?",
                             answer="Jasmin gym answer", keywords="gym training",
                             language="en"),
        ])
        db.session.commit()
        found = service._retrieve_relevant_knowledge("gym training", hostess.id, "en")
        missing = service._retrieve_relevant_knowledge("gym training", hostess.id, "ar")
    assert "Visit the gym" in found
    assert "Jasmin gym answer" in found
    assert "wrong language" in missing
    assert "Visit the gym" not in missing


def test_history_and_memory_retrieval_ignore_unsupported_rows(app, db, new_user):
    service = AIHostessService()
    with app.app_context():
        hostess = _hostess(db)
        db.session.add_all([
            HostessChatMessage(hostess_id=hostess.id, user_id=new_user.id,
                               role="user", content="first"),
            HostessChatMessage(hostess_id=hostess.id, user_id=new_user.id,
                               role="system", content="must not be replayed"),
            HostessChatMessage(hostess_id=hostess.id, user_id=new_user.id,
                               role="assistant", content="second"),
            HostessMemory(hostess_id=hostess.id, user_id=new_user.id,
                          key="likes", value="racing", importance=3),
        ])
        db.session.commit()
        history = service._fetch_persistent_history(hostess.id, new_user.id)
        memory = service._retrieve_relevant_memories(
            "what do I like?", hostess.id, new_user.id, "en")
    assert [x["role"] for x in history] == ["user", "assistant"]
    assert "must not" not in str(history)
    assert "- likes: racing" in memory


def test_fallback_and_greeting_paths_are_safe(app, db, monkeypatch):
    service = AIHostessService()
    with app.app_context():
        hostess = _hostess(db, intro_message="Hello | مرحبا")
        greeting = service.get_response("hello", hostess.to_dict(), {"id": 0})
        assert "Tell me what you want" in greeting

        monkeypatch.setitem(app.config, "OPENAI_API_KEY", "key")
        monkeypatch.setattr(service, "_call_openai", lambda *args: (_ for _ in ()).throw(
            RuntimeError("provider down")))
        fallback = service.get_response(
            "I feel sad", hostess.to_dict(), {"id": 0, "language": "en"},
            chat_history=[{"role": "user", "content": "previous"}])
    assert fallback
    assert "alone" in fallback.lower() or "plan" in fallback.lower()


def test_learning_extracts_and_updates_conversation_state(app, db, new_user):
    service = AIHostessService()
    with app.app_context():
        hostess = _hostess(db)
        service._auto_learn(
            hostess.id, new_user.id, "My name is Alex",
            "ok", hostess.to_dict(), {"id": new_user.id})
        service._auto_learn(
            hostess.id, new_user.id, "I like racing", "ok",
            hostess.to_dict(), {"id": new_user.id})
        service._update_conversation_state(
            hostess.id, new_user.id, "please be formal about racing",
            {"id": new_user.id})
        values = {(m.key, m.value) for m in HostessMemory.query.all()}
    assert ("name", "Alex") in values
    assert ("likes", "racing") in values
    assert ("preferred_tone", "formal") in values


def test_topic_tone_and_language_detection():
    service = AIHostessService()

    assert service._detect_topic("How do I register my account?") == "account"
    assert service._detect_topic("كيف أتمرن في الجيم؟") == "gym"
    assert service._detect_topic("I want to buy diamonds") == "economy_support"
    assert service._detect_tone("please be formal") == "formal"
    assert service._detect_tone("I feel anxious") == "emotional"
    assert service._resolve_language("مرحبا") == "ar"
    assert service._resolve_language("Hello there") == "en"


def test_jasmin_support_pitch_is_session_throttled(app):
    service = AIHostessService()
    with app.test_request_context("/"):
        first = service._maybe_append_support_pitch(
            "Answer", {"id": 4, "name": "Jasmin"}, {"id": 9}, "en")
        second = service._maybe_append_support_pitch(
            "Answer", {"id": 4, "name": "Jasmin"}, {"id": 9}, "en")
        guest = service._maybe_append_support_pitch(
            "Answer", {"id": 5, "name": "ياسمين"}, {"is_guest": True}, "ar")

        assert "support matters" in first
        assert second == "Answer"
        assert guest == "Answer"
        assert session["jasmin_support_pitch_at_4"]


def test_rule_based_jasmin_response_respects_language_and_tone(app):
    service = AIHostessService()
    with app.app_context():
        greeting = service._rule_based_response(
            "hello", {"id": 1, "name": "Jasmin"}, {"locale": "en"})
        formal = service._rule_based_response(
            "مرحبا، خليك رسمي", {"id": 1, "name": "ياسمين"}, {"locale": "ar"})

    assert greeting.startswith("Welcome.")
    assert "مرحباً" in formal
