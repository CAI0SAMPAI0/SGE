import json
import time
from django.conf import settings
from groq import Groq
from groq import RateLimitError, APIStatusError
from ai import prompts, models
from ai.tools import execute_tool, get_tool_schemas
from products.models import Product
from outflows.models import Outflow


def _groq_chat(client, **kwargs):
    max_retries = 4
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(**kwargs)
            return response.choices[0].message
        except RateLimitError:
            if attempt == max_retries - 1:
                raise
            delay = (2 ** attempt) + 1
            time.sleep(delay)
        except APIStatusError:
            if attempt == max_retries - 1:
                raise
            time.sleep(2 ** attempt)
    return None


class SGEAgent:

    def __init__(self, tenant=None):
        self.__client = Groq(
            api_key=settings.GROQ_API_KEY,
        )
        self.__tenant = tenant

    def __get_data(self):
        products = (
            Product.objects
            .select_related('brand', 'category')
            .order_by('quantity')[:20]
        )
        outflows = (
            Outflow.objects
            .select_related('product')
            .order_by('-created_at')[:30]
        )

        products_summary = [
            {
                'produto': p.title,
                'marca': p.brand.name,
                'estoque': p.quantity,
                'preco_venda': float(p.selling_price),
            }
            for p in products
        ]

        outflows_summary = [
            {
                'produto': o.product.title,
                'quantidade': o.quantity,
                'data': o.created_at.strftime('%Y-%m-%d'),
            }
            for o in outflows
        ]

        return json.dumps({
            'produtos': products_summary,
            'saidas': outflows_summary,
        }, ensure_ascii=False)

    def invoke(self):
        message = _groq_chat(
            self.__client,
            model=settings.GROQ_MODEL,
            messages=[
                {'role': 'system', 'content': prompts.SYSTEM_PROMPT},
                {'role': 'user', 'content': prompts.USER_PROMPT.replace('{{data}}', self.__get_data())},
            ],
            temperature=0.7,
        )
        result = message.content if message else 'Erro: sem resposta da IA.'
        models.AIResult.objects.create(result=result, tenant=self.__tenant)


class SGEChatAgent:

    def __init__(self, user):
        self.__client = Groq(api_key=settings.GROQ_API_KEY)
        self.__user = user

    def __build_messages(self, conversation, new_user_message):
        history = (
            models.ChatMessage.objects
            .filter(conversation=conversation)
            .order_by('created_at')
            .values_list('role', 'content')
        )
        messages = [{'role': 'system', 'content': prompts.CHAT_SYSTEM_PROMPT}]
        messages.extend({'role': r, 'content': c} for r, c in history)
        messages.append({'role': 'user', 'content': new_user_message})
        return messages

    def reply(self, conversation, user_message):
        messages = self.__build_messages(conversation, user_message)

        models.ChatMessage.objects.create(
            user=self.__user,
            conversation=conversation,
            role='user',
            content=user_message,
        )

        if not conversation.title or conversation.title == 'Nova conversa':
            conversation.title = user_message[:80]
            conversation.save(update_fields=['title'])

        assistant_content = self.__call_with_tools(messages, conversation.tenant)

        models.ChatMessage.objects.create(
            user=self.__user,
            conversation=conversation,
            role='assistant',
            content=assistant_content,
        )
        return assistant_content

    def __call_with_tools(self, messages, tenant=None, depth=0):
        if depth >= 3:
            return 'Não consegui completar a ação solicitada após várias tentativas.'

        message = _groq_chat(
            self.__client,
            model=settings.GROQ_MODEL,
            messages=messages,
            temperature=0.5,
            tools=get_tool_schemas(),
            tool_choice='auto',
        )
        if not message:
            return 'Erro: sem resposta da IA.'

        if message.tool_calls:
            messages.append(message)
            for tc in message.tool_calls:
                result = execute_tool(tc.function.name, json.loads(tc.function.arguments or '{}'), self.__user, tenant)
                messages.append({
                    'role': 'tool',
                    'tool_call_id': tc.id,
                    'content': json.dumps(result, ensure_ascii=False),
                })
            follow_up = _groq_chat(
                self.__client,
                model=settings.GROQ_MODEL,
                messages=messages,
                temperature=0.5,
            )
            return follow_up.content if follow_up else 'Erro: sem resposta da IA.'

        return message.content or 'Sem resposta.'

    def regenerate_from(self, conversation, message_id):
        """Trunca o historico a partir de message_id e regenera a resposta."""
        msg = models.ChatMessage.objects.get(pk=message_id, conversation=conversation)
        models.ChatMessage.objects.filter(
            conversation=conversation,
            created_at__gt=msg.created_at,
        ).delete()
        return self.reply(conversation, msg.content)

    def edit_and_resend(self, conversation, message_id, new_content):
        """Edita a mensagem do usuario e regenera a resposta da IA."""
        msg = models.ChatMessage.objects.get(pk=message_id, conversation=conversation, role='user')
        msg.content = new_content
        msg.save(update_fields=['content'])
        return self.regenerate_from(conversation, message_id)
