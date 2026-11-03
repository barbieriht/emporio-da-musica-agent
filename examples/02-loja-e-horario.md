# Informações da loja e se está aberta agora

Dados do manual (endereço) e consulta em tempo real ao horário de funcionamento.

- Provedor/modelo: `groq` / `openai/gpt-oss-120b`
- Gravado em: 2026-11-03 12:52
- Os blocos "🔧" mostram as ferramentas que o agente chamou (argumentos e resultado).

---

**Maestro:** Oi! Eu sou o Maestro, assistente virtual da Empório da Música. 🎸

Posso te ajudar com:
  • Preços, estoque e promoções dos instrumentos
  • Status do seu pedido (preciso do número do pedido e do telefone usado na compra)
  • Horários, endereço, formas de pagamento e parcelamento
  • Frete e prazos de entrega
  • Trocas, devoluções e garantia

Como posso ajudar?

**Cliente:** Qual o endereço da loja?

<details><summary>🔧 <code>get_policy(topic='loja')</code></summary>

```
# Sobre a Empório da Música

Loja especializada em instrumentos musicais, fundada em 2008 em Campo Grande, Mato Grosso do Sul. Mais de 15 anos de atuação, referência regional na venda de instrumentos para músicos iniciantes, intermediários e profissionais. Slogan: "Sua música começa aqui."

Catálogo: mais de 300 instrumentos de marcas nacionais e internacionais (guitarras, baixos, violões, baterias, teclados, instrumentos de sopro, cordas orquestrais e ukuleles). Trabalhamos exclusivamente com instrumentos musicais: não comercializamos acessórios como cordas, palhetas, cabos, cases, pedais ou  […]
```

</details>

**Maestro:** Claro! A Empório da Música fica na:

**Rua 14 de Maio, 3200 – Centro, Campo Grande – MS, CEP 79202‑333**

Se precisar falar com a gente, o telefone da loja é **(67) 3341‑4444** e o WhatsApp **(67) 3321‑4500**. Qualquer outra dúvida, é só chamar!

**Cliente:** E vocês estão abertos agora?

<details><summary>🔧 <code>is_store_open_now()</code></summary>

```
A loja está aberta agora.
```

</details>

**Maestro:** Sim, a loja está aberta agora. Precisa de alguma informação ou ajuda com algum instrumento?
