"""
LLM Service — Abstraction layer supporting Ollama, Anthropic Claude, and OpenAI.

All providers support streaming for real-time chat UX.
"""

import json
import logging
from abc import ABC, abstractmethod
from typing import AsyncGenerator, List, Optional

import httpx

from app.config import LLMProvider, settings

logger = logging.getLogger(__name__)


class BaseLLM(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    async def generate(self, messages: List[dict], system_prompt: str = "") -> str:
        """Generate a complete response."""
        ...

    @abstractmethod
    async def generate_stream(
        self, messages: List[dict], system_prompt: str = ""
    ) -> AsyncGenerator[str, None]:
        """Generate a streaming response, yielding tokens."""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the LLM provider is reachable."""
        ...


class OllamaLLM(BaseLLM):
    """Ollama local LLM provider."""

    def __init__(self, base_url: str = None, model: str = None):
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.model = model or settings.ollama_model
        self.client = httpx.AsyncClient(timeout=120.0)

    async def generate(self, messages: List[dict], system_prompt: str = "") -> str:
        msgs = self._prepare_messages(messages, system_prompt)
        response = await self.client.post(
            f"{self.base_url}/api/chat",
            json={"model": self.model, "messages": msgs, "stream": False},
        )
        response.raise_for_status()
        return response.json()["message"]["content"]

    async def generate_stream(
        self, messages: List[dict], system_prompt: str = ""
    ) -> AsyncGenerator[str, None]:
        msgs = self._prepare_messages(messages, system_prompt)
        async with self.client.stream(
            "POST",
            f"{self.base_url}/api/chat",
            json={"model": self.model, "messages": msgs, "stream": True},
            timeout=120.0,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.strip():
                    try:
                        data = json.loads(line)
                        if "message" in data and "content" in data["message"]:
                            token = data["message"]["content"]
                            if token:
                                yield token
                    except json.JSONDecodeError:
                        continue

    async def health_check(self) -> bool:
        try:
            resp = await self.client.get(f"{self.base_url}/api/tags", timeout=5.0)
            return resp.status_code == 200
        except Exception:
            return False

    def _prepare_messages(self, messages: List[dict], system_prompt: str) -> List[dict]:
        msgs = []
        if system_prompt:
            msgs.append({"role": "system", "content": system_prompt})
        msgs.extend(messages)
        return msgs


class AnthropicLLM(BaseLLM):
    """Anthropic Claude LLM provider."""

    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or settings.anthropic_api_key
        self.model = model or settings.anthropic_model
        if not self.api_key:
            raise ValueError("Anthropic API key is required. Set ANTHROPIC_API_KEY in .env")

    def _get_client(self):
        import anthropic
        return anthropic.AsyncAnthropic(api_key=self.api_key)

    async def generate(self, messages: List[dict], system_prompt: str = "") -> str:
        client = self._get_client()
        kwargs = {
            "model": self.model,
            "max_tokens": 4096,
            "messages": self._filter_messages(messages),
        }
        if system_prompt:
            kwargs["system"] = system_prompt
        response = await client.messages.create(**kwargs)
        return response.content[0].text

    async def generate_stream(
        self, messages: List[dict], system_prompt: str = ""
    ) -> AsyncGenerator[str, None]:
        client = self._get_client()
        kwargs = {
            "model": self.model,
            "max_tokens": 4096,
            "messages": self._filter_messages(messages),
        }
        if system_prompt:
            kwargs["system"] = system_prompt

        async with client.messages.stream(**kwargs) as stream:
            async for text in stream.text_stream:
                yield text

    async def health_check(self) -> bool:
        try:
            client = self._get_client()
            # Minimal request to verify key
            await client.messages.create(
                model=self.model,
                max_tokens=10,
                messages=[{"role": "user", "content": "Hi"}],
            )
            return True
        except Exception as e:
            logger.warning(f"Anthropic health check failed: {e}")
            return False

    def _filter_messages(self, messages: List[dict]) -> List[dict]:
        """Anthropic doesn't accept 'system' role in messages array."""
        return [m for m in messages if m["role"] in ("user", "assistant")]


class OpenAILLM(BaseLLM):
    """OpenAI LLM provider."""

    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or settings.openai_api_key
        self.model = model or settings.openai_model
        if not self.api_key:
            raise ValueError("OpenAI API key is required. Set OPENAI_API_KEY in .env")

    def _get_client(self):
        from openai import AsyncOpenAI
        return AsyncOpenAI(api_key=self.api_key)

    async def generate(self, messages: List[dict], system_prompt: str = "") -> str:
        client = self._get_client()
        msgs = []
        if system_prompt:
            msgs.append({"role": "system", "content": system_prompt})
        msgs.extend(messages)
        response = await client.chat.completions.create(
            model=self.model,
            messages=msgs,
            max_tokens=4096,
        )
        return response.choices[0].message.content

    async def generate_stream(
        self, messages: List[dict], system_prompt: str = ""
    ) -> AsyncGenerator[str, None]:
        client = self._get_client()
        msgs = []
        if system_prompt:
            msgs.append({"role": "system", "content": system_prompt})
        msgs.extend(messages)
        stream = await client.chat.completions.create(
            model=self.model,
            messages=msgs,
            max_tokens=4096,
            stream=True,
        )
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def health_check(self) -> bool:
        try:
            client = self._get_client()
            await client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=5,
            )
            return True
        except Exception as e:
            logger.warning(f"OpenAI health check failed: {e}")
            return False


# ─── Factory & Runtime State ─────────────────────────────

class LLMManager:
    """Manages the active LLM provider with runtime switching."""

    def __init__(self):
        self._provider: LLMProvider = settings.llm_provider
        self._custom_model: Optional[str] = None
        self._custom_api_key: Optional[str] = None
        self._instance: Optional[BaseLLM] = None

    @property
    def provider(self) -> LLMProvider:
        return self._provider

    @property
    def model_name(self) -> str:
        if self._custom_model:
            return self._custom_model
        if self._provider == LLMProvider.OLLAMA:
            return settings.ollama_model
        elif self._provider == LLMProvider.ANTHROPIC:
            return settings.anthropic_model
        else:
            return settings.openai_model

    def get_llm(self) -> BaseLLM:
        """Get the current LLM instance (creates lazily)."""
        if self._instance is None:
            self._instance = self._create_instance()
        return self._instance

    def switch_provider(
        self, provider: str, model: str = None, api_key: str = None
    ):
        """Switch the active LLM provider at runtime."""
        self._provider = LLMProvider(provider)
        self._custom_model = model
        self._custom_api_key = api_key
        self._instance = None  # Force re-creation
        logger.info(f"Switched LLM provider to {provider} (model: {model or 'default'})")

    def _create_instance(self) -> BaseLLM:
        if self._provider == LLMProvider.OLLAMA:
            return OllamaLLM(model=self._custom_model)
        elif self._provider == LLMProvider.ANTHROPIC:
            return AnthropicLLM(
                api_key=self._custom_api_key,
                model=self._custom_model,
            )
        elif self._provider == LLMProvider.OPENAI:
            return OpenAILLM(
                api_key=self._custom_api_key,
                model=self._custom_model,
            )
        else:
            raise ValueError(f"Unknown LLM provider: {self._provider}")


# Singleton manager
llm_manager = LLMManager()


class MockLLM(BaseLLM):
    """Fallback simulated LLM provider to ensure the app is fully demoable offline."""

    async def generate(self, messages: List[dict], system_prompt: str = "") -> str:
        user_msg = messages[-1]["content"] if messages else ""
        return self._get_mock_response(user_msg, system_prompt)

    async def generate_stream(
        self, messages: List[dict], system_prompt: str = ""
    ) -> AsyncGenerator[str, None]:
        import asyncio
        user_msg = messages[-1]["content"] if messages else ""
        response = self._get_mock_response(user_msg, system_prompt)
        
        # Stream response word-by-word with delay to simulate real LLM generation
        words = response.split(" ")
        for word in words:
            yield word + " "
            await asyncio.sleep(0.02)  # Fast typist speed

    async def health_check(self) -> bool:
        return True

    def _get_mock_response(self, user_msg: str, system_prompt: str) -> str:
        msg_lower = user_msg.lower()
        
        # Determine intent from system prompt or message content
        is_ship30 = "ship30" in system_prompt.lower() or "essay" in msg_lower or "ship 30" in msg_lower
        is_artifact = "artifact" in system_prompt.lower() or "create" in msg_lower or "generate" in msg_lower or "html" in msg_lower

        if is_ship30:
            return self._mock_ship30_essay(user_msg)
        elif is_artifact:
            return self._mock_artifact(user_msg)
        else:
            return self._mock_qa(user_msg)

    def _mock_ship30_essay(self, topic: str) -> str:
        return f"""Most startups get growth completely wrong. They think it's a funnel. It's actually a loop.

Here is the exact **growth loop framework** top companies use to scale compoundingly, based on insights from Lenny's Podcast.

### The Death of the Funnel
The traditional acquisition funnel is a leaky bucket. You pour traffic in, some convert, and the rest drop off. **If you stop buying traffic, growth stops instantly.**

Lenny's guests (like Brian Balfour and Casey Winters) point out that **funnels build linear growth, whereas loops build exponential growth**.

A loop is self-reinforcing:
1. **New User** joins the platform.
2. They take a **Core Action** (e.g., share a link, invite a teammate).
3. This action creates a **Trigger** or output.
4. The output brings in **More Users**, and the cycle restarts.

---

### Three Core Growth Loops Every PM Must Master

According to growth experts on Lenny's Podcast, there are three dominant loops:

#### 1. The Viral Loop
This occurs when a user naturally invites others as part of using the product.
- **Example:** Zoom or Slack. You can't use the product without inviting others.
- **Actionable Advice:** Make the invitation flow frictionless. Every click removed increases your viral coefficient ($K$).

#### 2. The Content Loop
This is fueled by user-generated content (UGC) indexable by search engines.
- **Example:** Pinterest or TripAdvisor. Users create content → search engines index it → searchers find it and sign up → new users create more content.
- **Actionable Advice:** Optimize search indexing templates and structure URL hierarchy logically.

#### 3. The Paid Loop
This uses revenue generated from active users to buy more users.
- **Example:** E-commerce brands. LTV is used to fund CAC.
- **Actionable Advice:** Monitor payback periods. The best companies keep payback periods under 6 months.

---

### The Takeaway
Stop optimizing your funnel. Start building your loop. **Your loops are your product's engine.** 

If you can connect your product's core value directly back to acquisition, growth will take care of itself.

<artifact type="markdown" title="Ship30for30 Essay: The Power of Growth Loops">
# Stop Optimizing Funnels: Why Loops Are the Real Engine of Product Growth

Most startups get growth completely wrong. They think it's a funnel. It's actually a loop.

Here is the exact **growth loop framework** top companies use to scale compoundingly, based on insights from Lenny's Podcast.

## The Death of the Funnel
The traditional acquisition funnel is a leaky bucket. You pour traffic in, some convert, and the rest drop off. **If you stop buying traffic, growth stops instantly.**

Lenny's guests (like Brian Balfour and Casey Winters) point out that **funnels build linear growth, whereas loops build exponential growth**.

A loop is self-reinforcing:
1. **New User** joins the platform.
2. They take a **Core Action** (e.g., share a link, invite a teammate).
3. This action creates a **Trigger** or output.
4. The output brings in **More Users**, and the cycle restarts.

---

## Three Core Growth Loops Every PM Must Master

According to growth experts on Lenny's Podcast, there are three dominant loops:

### 1. The Viral Loop
This occurs when a user naturally invites others as part of using the product.
- **Example:** Zoom or Slack. You can't use the product without inviting others.
- **Actionable Advice:** Make the invitation flow frictionless. Every click removed increases your viral coefficient ($K$).

### 2. The Content Loop
This is fueled by user-generated content (UGC) indexable by search engines.
- **Example:** Pinterest or TripAdvisor. Users create content → search engines index it → searchers find it and sign up → new users create more content.
- **Actionable Advice:** Optimize search indexing templates and structure URL hierarchy logically.

### 3. The Paid Loop
This uses revenue generated from active users to buy more users.
- **Example:** E-commerce brands. LTV is used to fund CAC.
- **Actionable Advice:** Monitor payback periods. The best companies keep payback periods under 6 months.

---

## The Takeaway
Stop optimizing your funnel. Start building your loop. **Your loops are your product's engine.** 

If you can connect your product's core value directly back to acquisition, growth will take care of itself.
</artifact>"""

    def _mock_artifact(self, topic: str) -> str:
        return """Here is a complete, custom dashboard mapping out key metrics and frameworks for finding product-market fit, synthesized from Lenny's Podcast interviews with leading experts:

<artifact type="html" title="Product-Market Fit (PMF) Metrics Dashboard">
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>PMF Metrics Dashboard</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0f172a;
            color: #f1f5f9;
            margin: 0;
            padding: 24px;
        }
        .dashboard {
            max-width: 1000px;
            margin: 0 auto;
        }
        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid #334155;
            padding-bottom: 16px;
            margin-bottom: 24px;
        }
        h1 {
            font-size: 24px;
            margin: 0;
            background: linear-gradient(135deg, #a78bfa, #6c5ce7);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 20px;
            margin-bottom: 24px;
        }
        .card {
            background: #1e293b;
            border: 1px solid #334155;
            border-radius: 12px;
            padding: 20px;
        }
        .card-title {
            font-size: 14px;
            color: #94a3b8;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 8px;
        }
        .card-value {
            font-size: 32px;
            font-weight: bold;
            color: #a78bfa;
            margin-bottom: 8px;
        }
        .card-desc {
            font-size: 13px;
            color: #64748b;
            line-height: 1.4;
        }
        .framework-box {
            background: #1e293b;
            border: 1px solid #334155;
            border-radius: 12px;
            padding: 24px;
            margin-top: 24px;
        }
        .framework-box h2 {
            margin-top: 0;
            font-size: 18px;
            color: #f1f5f9;
        }
        ul {
            padding-left: 20px;
            margin-bottom: 0;
        }
        li {
            margin-bottom: 8px;
            color: #cbd5e1;
            font-size: 14px;
        }
    </style>
</head>
<body>
    <div class="dashboard">
        <header>
            <h1>Product-Market Fit (PMF) Metrics</h1>
            <span style="font-size:12px;color:#64748b;">Source: Lenny's Podcast</span>
        </header>
        
        <div class="metrics-grid">
            <div class="card">
                <div class="card-title">Sean Ellis Test</div>
                <div class="card-value">&ge; 40%</div>
                <div class="card-desc">Percentage of users who would be <strong>"very disappointed"</strong> if they could no longer use your product. Critical leading indicator of PMF.</div>
            </div>
            
            <div class="card">
                <div class="card-title">Cohorted Retention</div>
                <div class="card-value">Flat Curve</div>
                <div class="card-desc">Your cohort retention curve must <strong>flatten out parallel to the x-axis</strong> (e.g. 20-40% active at 12 months), proving long-term utility.</div>
            </div>
            
            <div class="card">
                <div class="card-title">Net Promoter Score</div>
                <div class="card-value">&gt; 50</div>
                <div class="card-desc">Word-of-mouth coefficient. A high NPS index indicates organic viral recommendation engine is active.</div>
            </div>
        </div>

        <div class="framework-box">
            <h2>The 3 Pillars of PMF (Andy Rachleff Framework)</h2>
            <ul>
                <li><strong>Market Urgency:</strong> Are you solving a "hair on fire" problem where customers are desperate for any solution?</li>
                <li><strong>Product Utility:</strong> Does the product deliver 10x value compared to existing workarounds?</li>
                <li><strong>Organic Distribution:</strong> Are users recommending it to their colleagues without paid loops?</li>
            </ul>
        </div>
    </div>
</body>
</html>
</artifact>"""

    def _mock_qa(self, query: str) -> str:
        # Check topic keywords for specific transcript answers
        if "market fit" in query.lower() or "pmf" in query.lower():
            return """Based on transcripts from Lenny's Podcast, here are the best frameworks for finding and measuring **Product-Market Fit (PMF)**:

### 1. The Sean Ellis Test (40% Rule)
As discussed in several growth episodes, the Sean Ellis survey asks active users: *"How would you feel if you could no longer use the product?"* 
- **The Metric**: If **&ge; 40%** answer *"Very Disappointed"*, you have crossed the threshold of baseline product-market fit.
- **Actionable Advice**: Run this survey after a user has performed your product's "core value action" at least 3 times.

### 2. Cohort Retention Flattening (Brian Balfour)
Brian Balfour emphasizes that the absolute best metric for PMF is cohort retention:
- **The Curve**: Plot your retention curve over time. If it continues to slope downward towards zero, you do NOT have PMF.
- **The Fit**: The curve must **flatten out** (e.g., at 30% retention) and remain flat for months. This proves users find permanent, recurring value.

### 3. The "Hair on Fire" Framework (Michael Seibel)
If your house is on fire and someone offers you a brick to put it out, you will buy the brick and hit yourself on the head with it.
- **The Urgency**: Are your customers using buggy, incomplete prototypes because they are desperate for any solution to their pain? If so, you are in a high-urgency market.

Always ground your early product iterations in solving this singular, acute pain point before expanding your feature set. Let me know if you would like me to draft a Ship30-style essay on this!"""

        elif "priorit" in query.lower():
            return """In Lenny's Podcast interviews, top product leaders (such as Shreyas Doshi and Ken Norton) emphasize that prioritization is less about frameworks (like RICE or MoSCoW) and more about **strategic alignment and resource leverage**.

### 1. LNO Prioritization (Shreyas Doshi)
Shreyas Doshi recommends classifying your tasks into three categories:
- **L (Leverage Tasks)**: Critical tasks that yield 10x impact. You should spend 80% of your creative energy here.
- **N (Neutral Tasks)**: Normal execution tasks. Must be done well, but won't change the trajectory of the company.
- **O (Overhead Tasks)**: Administrative work. Do these as quickly and minimally as possible.

### 2. The Rock, Pebble, Sand Analogy
- **Rocks**: Your 1-2 major strategic initiatives for the quarter (e.g. launch a new market segment).
- **Pebbles**: Small features and product improvements.
- **Sand**: Bug fixes, minor visual tweaks, and maintenance.
- **Actionable Tip**: If you fill your jar with sand first, you won't have room for the rocks. **Always plan your rocks first.**

### 3. Customer Problem Stack Ranking
Instead of feature lists, stack rank customer *problems*.
- **The Focus**: Focus your engineering team on solving the top **2 customer problems** completely, rather than partially solving 10 different problems.

Would you like me to build a visual infographic component summarizing these prioritization techniques? Just ask me to "create a visual comparison component"!"""

        else:
            return f"""Insights from Lenny's Podcast guests suggest that when dealing with *"{query}"*, product and growth leaders focus on **high leverage, clear metric definition, and iterative loops**.

To give you a structured summary:
1. **Define the Core Loop**: Identify how action A leads to outcome B and feeds back into A.
2. **Set a Single Focus Metric (North Star)**: Don't track 10 things. Pick the one metric that best represents value delivered to the user.
3. **Friction Reduction**: Casey Winters points out that removing 1 step from your onboarding funnel is worth more than adding 5 new features.

Would you like me to write a full Ship30for30 style essay summarizing these concepts, or generate a custom visual dashboard artifact?"""

