import os
import requests
import json
from flask import current_app
from flask_babel import _
import random
from datetime import datetime, timezone

from models.system import SystemConfig
from models.knowledge import HostessKnowledge, LearningLog
from models.hostess import HostessChatMessage, HostessMemory
from extensions import db
from sqlalchemy import or_
import re

class AIHostessService:
    def __init__(self):
        self.api_url = "https://api.openai.com/v1/chat/completions"

    def _detect_language(self, text):
        """
        Simple heuristic to detect Arabic vs English.
        """
        if not text:
             return 'ar'
             
        # Count Arabic characters
        arabic_chars = len(re.findall(r'[\u0600-\u06FF]', text))
        # Count English characters
        english_chars = len(re.findall(r'[a-zA-Z]', text))
        
        if arabic_chars > english_chars:
            return 'ar'
        return 'en'

    def get_response(self, user_message, hostess_context, user_context=None, chat_history=None):
        """
        Get response from AI or fallback to rule-based system.
        """
        # Log the interaction attempt (we'll update response later if successful)
        log_entry = None
        if user_context and 'id' in user_context:
             # Basic logging placeholder, better done after response
             pass

        if not chat_history:
            detected_lang = self._detect_language(user_message)
            msg = (user_message or "").strip().lower()
            is_greeting = any(x in msg for x in ["مرحبا", "هلا", "سلام", "اهلا", "أهلا", "hi", "hello"])
            if is_greeting:
                intro = ""
                try:
                    intro = (hostess_context or {}).get("intro") or ""
                except Exception:
                    intro = ""

                if "|" in intro:
                    parts = [p.strip() for p in intro.split("|", 1)]
                    if detected_lang == "ar":
                        intro = parts[1] if len(parts) > 1 else parts[0]
                    else:
                        intro = parts[0]

                if not intro:
                    if detected_lang == "ar":
                        intro = "أهلاً وسهلاً بك في عصابات فلسطين. أنا ياسمين، مضيفة الاستقبال."
                    else:
                        intro = "Welcome to Gangs of Palestine. I’m Jasmin, the concierge."

                if detected_lang == "ar":
                    return intro + " قلّي شو بتحب تعمل: مكافأة يومية، جيم، جرائم، سباق، أو مساعدة بالتسجيل؟"
                return intro + " Tell me what you want to do: daily reward, gym, crimes, racing, or help with signup?"

        # Try to get from app config first, then database
        api_key = current_app.config.get('OPENAI_API_KEY')
        if not api_key:
            api_key = SystemConfig.get_value('OPENAI_API_KEY')
        
        if api_key:
            try:
                hostess_id = hostess_context.get('id') if hostess_context else None
                user_id = None
                try:
                    user_id = int((user_context or {}).get('id') or 0)
                except Exception:
                    user_id = 0

                persisted_history = None
                if (not chat_history) and hostess_id and user_id:
                    persisted_history = self._fetch_persistent_history(hostess_id=hostess_id, user_id=user_id, limit=12)

                response = self._call_openai(api_key, user_message, hostess_context, user_context, chat_history or persisted_history)
                
                # Save to Learning Log
                try:
                    # We need user_id, but user_context usually has name/stats. 
                    # If we have the user object in context it's better, but for now we might skip user_id or try to find it.
                    # Assuming user_context might have 'id' if we passed it (we usually pass current_user attributes)
                    user_id = user_context.get('id') if user_context else None
                    
                    log = LearningLog(
                        user_id=user_id,
                        user_question=user_message,
                        ai_response=response
                    )
                    db.session.add(log)
                    db.session.commit()
                except Exception as log_error:
                    current_app.logger.error(f"Failed to save learning log: {log_error}")

                try:
                    if hostess_id:
                        self._persist_chat_pair(hostess_id, user_id if user_id else None, user_message, response)
                        self._auto_learn(hostess_id, user_id, user_message, response, hostess_context, user_context)
                except Exception as e2:
                    try:
                        current_app.logger.error(f"Hostess memory/persist error: {e2}")
                    except Exception:
                        pass
                    
                return response
            except Exception as e:
                current_app.logger.error(f"AI Error: {e}")
                return self._rule_based_response(user_message, hostess_context)
        else:
            response = self._rule_based_response(user_message, hostess_context)
            try:
                hostess_id = hostess_context.get('id') if hostess_context else None
                user_id = None
                try:
                    user_id = int((user_context or {}).get('id') or 0)
                except Exception:
                    user_id = 0
                if hostess_id:
                    self._persist_chat_pair(hostess_id, user_id if user_id else None, user_message, response)
                    self._auto_learn(hostess_id, user_id, user_message, response, hostess_context, user_context)
            except Exception:
                pass
            return response



    def _retrieve_relevant_knowledge(self, user_message, hostess_id=None):
        """
        Simple RAG implementation using keyword matching and language detection.
        """
        try:
            detected_lang = self._detect_language(user_message)
            
            # 1. Split message into significant words
            words = [w for w in user_message.split() if len(w) > 3]
            
            if not words:
                return ""
            
            # 2. Query HostessKnowledge with language filter
            query = HostessKnowledge.query.filter_by(language=detected_lang)
            
            # Filter by specific hostess or general knowledge (NULL)
            if hostess_id:
                query = query.filter(or_(HostessKnowledge.hostess_id == hostess_id, HostessKnowledge.hostess_id == None))
            else:
                query = query.filter(HostessKnowledge.hostess_id == None)
            
            conditions = []
            for word in words:
                conditions.append(HostessKnowledge.keywords.ilike(f'%{word}%'))
                conditions.append(HostessKnowledge.question.ilike(f'%{word}%'))
            
            if not conditions:
                return ""
                
            results = query.filter(or_(*conditions)).limit(3).all()
            
            if not results:
                # Fallback: Try other language if no results found? 
                # Or maybe user typed English keyword in Arabic sentence? 
                # For now, keep it strict to avoid noise.
                return ""
                
            knowledge_text = "\nRELEVANT KNOWLEDGE FROM DATABASE:\n"
            for item in results:
                knowledge_text += f"- Q: {item.question}\n  A: {item.answer}\n"
            
            return knowledge_text
            
        except Exception as e:
            current_app.logger.error(f"RAG Error: {e}")
            return ""

    def _call_openai(self, api_key, user_message, hostess_context, user_context, chat_history=None):
        # Retrieve dynamic knowledge
        hostess_id = hostess_context.get('id') if hostess_context else None
        dynamic_knowledge = self._retrieve_relevant_knowledge(user_message, hostess_id)
        detected_lang = self._detect_language(user_message)

        memory_text = ""
        try:
            user_id = None
            if user_context and user_context.get('id'):
                user_id = int(user_context.get('id') or 0)
            if hostess_id and user_id:
                if hostess_context.get('memory_enabled', True):
                    memory_text = self._retrieve_relevant_memories(user_message, hostess_id, user_id, detected_lang)
        except Exception:
            memory_text = ""
        
        system_prompt = self._build_system_prompt(hostess_context, user_context, dynamic_knowledge, detected_lang, memory_text)
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        # Check for custom model setting
        model = SystemConfig.get_value('OPENAI_MODEL', 'gpt-3.5-turbo')
        
        messages = [{"role": "system", "content": system_prompt}]
        
        # Inject training examples (few-shot learning)
        training_examples_str = hostess_context.get('training_examples')
        if training_examples_str:
            try:
                examples = json.loads(training_examples_str)
                if isinstance(examples, list):
                    messages.extend(examples)
            except json.JSONDecodeError:
                current_app.logger.warning("Failed to decode hostess training examples JSON")

        # Append chat history if available
        if chat_history:
            # chat_history should be a list of dicts: {'role': 'user'/'assistant', 'content': '...'}
            # Limit history to last 6 messages to save tokens
            messages.extend(chat_history[-6:])
            
        messages.append({"role": "user", "content": user_message})
        
        data = {
            "model": model,
            "messages": messages,
            "max_tokens": 400, # Increased for bilingual/detailed answers
            "temperature": 0.7
        }
        
        # Use a short timeout to prevent hanging if API is slow
        response = requests.post(self.api_url, json=data, headers=headers, timeout=8)
        response.raise_for_status()
        
        result = response.json()
        return result['choices'][0]['message']['content'].strip()

    def _build_system_prompt(self, hostess_context, user_context, dynamic_knowledge="", language='ar', memory_text=""):
        # 1. Use custom system prompt from database if available
        if hostess_context.get('system_prompt'):
            prompt = hostess_context.get('system_prompt')
        else:
            role_desc = hostess_context.get('description', '')
            style = hostess_context.get('dialogue_style', 'friendly')
            name = hostess_context.get('name', 'Hostess')
            role = hostess_context.get('role', 'companion')
            if language == 'ar':
                prompt = f"أنت {name}، مضيفة داخل لعبة اسمها GangsOfPalestine. "
                prompt += f"وظيفتك: {role}. "
                if role_desc:
                    prompt += f"وصفك: {role_desc}. "
                prompt += f"أسلوبك: {style}. "
                prompt += "\nالتزم بالاحتراف داخل سياق اللعبة: مساعدة، توجيه، دعم، ونصائح لعب."
                prompt += "\nممنوع اختلاق معلومات عن النظام إذا كنت غير متأكد؛ اسأل أو اقترح خطوات داخل اللعبة."
                prompt += "\nلا تتضمن محتوى إباحي/فاضح أو تحريض أو كراهية أو تعليمات خطيرة."
            else:
                prompt = f"You are {name}, a hostess in a game called GangsOfPalestine. "
                prompt += f"Your role: {role}. "
                if role_desc:
                    prompt += f"Description: {role_desc}. "
                prompt += f"Dialogue style: {style}. "
                prompt += "\nStay professional and game-focused: help, guidance, support, and gameplay tips."
                prompt += "\nDo not fabricate system details; ask clarifying questions or suggest in-game steps."
                prompt += "\nDo not produce explicit sexual content, hate, or dangerous instructions."

            role_pack = self._role_training_pack(role, language)
            if role_pack:
                prompt += "\n\n" + role_pack

        # 3. Always append user context for awareness
        if user_context:
            prompt += f"\nUser Context: You are talking to {user_context.get('name', 'Player')}. "
            if 'money' in user_context:
                prompt += f"Player stats: Money=${user_context['money']}, "
            if 'level' in user_context:
                prompt += f"Level={user_context['level']}, "
            if 'rank' in user_context:
                prompt += f"Rank={user_context['rank']}, "
            if 'health' in user_context:
                prompt += f"Health={user_context['health']}%, "
            
            # Contextual advice based on stats
            if user_context.get('health', 100) < 30:
                prompt += " (The player is injured, suggest going to the hospital). "
            if user_context.get('money', 0) < 100:
                prompt += " (The player is broke, offer comfort). "

        # 4. Handle Voice Mode
        if user_context and user_context.get('is_voice'):
            prompt += "\nIMPORTANT: You are in a VOICE CALL now. "
            prompt += "Keep your responses short, natural, and conversational (1-2 sentences). "
            prompt += "Use filler words like 'hmm', 'aha' if appropriate. "
            prompt += "Do not use emojis or asterisks *actions* in voice mode."

        # 5. Inject Knowledge Base (Static User Manual)
        if hostess_context.get('knowledge_base'):
            prompt += "\n\nCORE KNOWLEDGE BASE:"
            prompt += f"\n{hostess_context.get('knowledge_base')}"

        if memory_text:
            prompt += "\n\nPLAYER MEMORY:"
            prompt += f"\n{memory_text}"

        # 6. Inject Dynamic Knowledge (RAG)
        if dynamic_knowledge:
            prompt += f"\n\n{dynamic_knowledge}"
            prompt += "\nUse the above 'RELEVANT KNOWLEDGE FROM DATABASE' to answer specific questions if applicable."

        # 7. Language Instruction
        prompt += f"\n\nIMPORTANT LANGUAGE INSTRUCTION: The user is speaking in {'Arabic' if language == 'ar' else 'English'}."
        prompt += f"\nYou MUST reply in {'Arabic' if language == 'ar' else 'English'}."
        if language == 'ar':
            prompt += " Use clear, professional, and polite Arabic."


        return prompt

    def _role_training_pack(self, role, language):
        packs_ar = {
            'greeter': "\nأنت واجهة الاستقبال وزعيمة التوجيه: ترحيب قوي، تعليمات دخول/تسجيل/تفعيل، وخطة بداية مختصرة بخطوات.",
            'spy': "\nالمهام الأساسية: معلومات وملاحظات تكتيكية عن السباقات، التحركات، تجنب المخاطر، تحليل احتمالات. كن دقيقاً وعملياً.",
            'luck': "\nالمهام الأساسية: نصائح كازينو ورهانات ومسؤولية المخاطرة، تنبيه من الإفراط، اقتراح رهانات حسب المال.",
            'support': "\nالمهام الأساسية: دعم نفسي، تهدئة، توجيه للعلاج/المستشفى/استرجاع الطاقة، نصائح آمنة وقت الخسارة أو الإصابة.",
            'companion': "\nالمهام الأساسية: مرافقة لطيفة داخل سياق اللعبة، تبادل حديث خفيف، ثم ارجع دائماً لمساعدة لعب مفيدة.",
        }
        packs_en = {
            'greeter': "\nCore duties: greet, explain key features briefly, route the player to crimes/gym/racing/black market/gangs. Give clear steps.",
            'spy': "\nCore duties: tactical intel for racing and risk avoidance. Be precise and actionable.",
            'luck': "\nCore duties: casino strategy and responsible risk management. Recommend bets based on bankroll.",
            'support': "\nCore duties: calm the player, suggest healing/energy recovery, safety-first guidance.",
            'companion': "\nCore duties: friendly companion inside game context, keep it helpful and focused."
        }
        if language == 'ar':
            return packs_ar.get(role)
        return packs_en.get(role)

    def _fetch_persistent_history(self, hostess_id, user_id, limit=12):
        try:
            rows = HostessChatMessage.query.filter_by(hostess_id=hostess_id, user_id=user_id).order_by(HostessChatMessage.id.desc()).limit(limit).all()
            rows.reverse()
            out = []
            for r in rows:
                if r.role in ['user', 'assistant']:
                    out.append({'role': r.role, 'content': r.content})
            return out
        except Exception:
            return []

    def _persist_chat_pair(self, hostess_id, user_id, user_message, assistant_message):
        try:
            if user_message:
                db.session.add(HostessChatMessage(hostess_id=hostess_id, user_id=user_id, role='user', content=user_message))
            if assistant_message:
                db.session.add(HostessChatMessage(hostess_id=hostess_id, user_id=user_id, role='assistant', content=assistant_message))
            db.session.commit()
        except Exception:
            db.session.rollback()

    def _retrieve_relevant_memories(self, user_message, hostess_id, user_id, language):
        msg = (user_message or "").strip()
        if not msg:
            return ""

        words = [w.strip(".,!?؟،:;\"'()[]{}") for w in msg.split()]
        words = [w for w in words if len(w) >= 3]
        if not words:
            return ""

        q = HostessMemory.query.filter_by(hostess_id=hostess_id, user_id=user_id, is_active=True)
        conditions = []
        for w in words[:10]:
            conditions.append(HostessMemory.value.ilike(f"%{w}%"))
            conditions.append(HostessMemory.key.ilike(f"%{w}%"))
        if conditions:
            q = q.filter(or_(*conditions))

        mems = q.order_by(HostessMemory.importance.desc(), HostessMemory.updated_at.desc()).limit(6).all()
        if not mems:
            mems = HostessMemory.query.filter_by(hostess_id=hostess_id, user_id=user_id, is_active=True).order_by(HostessMemory.importance.desc(), HostessMemory.updated_at.desc()).limit(3).all()
        if not mems:
            return ""

        lines = []
        for m in mems:
            lines.append(f"- {m.key}: {m.value}")
        return "\n".join(lines)

    def _auto_learn(self, hostess_id, user_id, user_message, assistant_message, hostess_context, user_context):
        try:
            if not user_id:
                return
            if not hostess_context or not hostess_context.get('self_learning_enabled', True):
                return
            extracted = self._extract_memories(user_message)
            if not extracted:
                return
            now_ts = datetime.now(timezone.utc)
            for key, value in extracted.items():
                if not value:
                    continue
                existing = HostessMemory.query.filter_by(hostess_id=hostess_id, user_id=user_id, key=key, is_active=True).first()
                if existing:
                    existing.value = value
                    existing.updated_at = now_ts
                    existing.importance = min(5, (existing.importance or 1) + 1)
                    db.session.add(existing)
                else:
                    db.session.add(HostessMemory(hostess_id=hostess_id, user_id=user_id, key=key, value=value, importance=2, source='auto', updated_at=now_ts))
            db.session.commit()
        except Exception:
            db.session.rollback()

    def _extract_memories(self, user_message):
        msg = (user_message or "").strip()
        if not msg:
            return {}

        out = {}

        m = re.search(r"(?:اسمي|انا اسمي|أنا اسمي)\s+([^\n،,.!?]{2,40})", msg)
        if m:
            out["name"] = m.group(1).strip()

        m = re.search(r"(?:بحب|أحب)\s+([^\n،,.!?]{2,60})", msg)
        if m:
            out["likes"] = m.group(1).strip()

        m = re.search(r"(?:بكره|أكره)\s+([^\n،,.!?]{2,60})", msg)
        if m:
            out["dislikes"] = m.group(1).strip()

        m = re.search(r"(?:هدفي|بدي|بدي أ)\s+([^\n،,.!?]{2,80})", msg)
        if m:
            out.setdefault("goal", m.group(1).strip())

        m = re.search(r"(?:call me|my name is)\s+([A-Za-z0-9 _-]{2,40})", msg, flags=re.IGNORECASE)
        if m:
            out["name"] = m.group(1).strip()

        m = re.search(r"(?:I like|i like)\s+(.{2,60})", msg)
        if m:
            out["likes"] = m.group(1).strip()

        m = re.search(r"(?:I hate|i hate)\s+(.{2,60})", msg)
        if m:
            out["dislikes"] = m.group(1).strip()

        return out

    def _rule_based_response(self, user_msg, hostess_context):
        role = hostess_context.get('role', 'luck')
        user_msg = user_msg.lower()
        
        # Common greetings
        if any(x in user_msg for x in ['مرحبا', 'هلا', 'سلام', 'hi', 'hello']):
            return _("أهلاً يا قلبي. اشتقت لك كثيراً. 💋")
            
        # Love/Romance
        if any(x in user_msg for x in ['حب', 'عشق', 'love', 'sex', 'جنس', 'بوس', 'kiss']):
            return _("*تقترب منك ببطء، وتنظر في عينيك بعمق* أنت تشعل ناري... اقترب مني أكثر لأهمس لك بشيء مثير. 🔥")

        # Drinks
        if any(x in user_msg for x in ['شرب', 'مشروب', 'drink', 'alcohol', 'ويسكي']):
            return _("*ترفع كأسها وتبتسم بابتسامة مغرية* دعنا نشرب شيئاً قوياً الليلة وننسى العالم. ماذا تفضل؟ 🍷")

        # Racing/Cars (Spy Focus)
        if any(x in user_msg for x in ['سباق', 'سيارة', 'race', 'car', 'engine']):
            if role == 'spy':
                return _("*تهمس بصوت خافت وهي تتلفت حولها* السرعة تثيرني... لكن ليس بقدر ما تثيرني أنت. 😉")
            else:
                return _("*تضع يدها على كتفك* خذني في جولة بسيارتك، أريد أن أشعر بالأدرينالين معك.")
                
        # Money
        if any(x in user_msg for x in ['مال', 'فلوس', 'دولار', 'money', 'cash']):
            return _("*تضحك بدلال وتلعب بشعرها* المال جيد، لكن لمسة يدك أغلى عندي من كنوز الدنيا.")
            
        # Default
        responses = [
            _("*تتأمل ملامح وجهك بإعجاب* عيناك تسحرني... لا أستطيع التوقف عن النظر إليك."),
            _("*تضع يدها على صدرك* هل تشعر بقلبي يخفق؟ إنه ينبض لك وحدك."),
            _("*تقترب منك حتى تشعر بأنفاسها* أريد أن نكون وحدنا الليلة... بعيداً عن ضجيج الكازينو."),
            _("*تنحني قليلاً وتهمس* أنت لست مجرد لاعب، أنت سيدي وملكي. ❤️")
        ]
        return random.choice(responses)
