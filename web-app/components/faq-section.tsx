"use client"

import type React from "react"
import { useState } from "react"
import { ChevronDown } from "lucide-react"

const faqData = [
  {
    question: "What is OpenProxyAI and who is it for?",
    answer:
      "OpenProxyAI is a Zero Trust Gateway that sits between your enterprise users and LLM providers like OpenAI, Anthropic, and Azure. It's designed for CISOs, security teams, and IT leaders in regulated industries — finance, healthcare, government — who need to deploy AI safely with full compliance, audit trails, and cost controls.",
  },
  {
    question: "How does the proxy architecture work?",
    answer:
      "OpenProxyAI acts as a transparent reverse proxy. Your developers use a single unified API endpoint instead of connecting directly to LLM providers. Every request passes through our policy engine — which enforces PII detection, content filtering, model restrictions, and budget controls — before being routed to the appropriate LLM provider. Responses flow back through the same pipeline for logging and compliance.",
  },
  {
    question: "Which LLM providers are supported?",
    answer:
      "OpenProxyAI supports all major providers through a unified API: OpenAI (GPT-4, GPT-4o), Anthropic (Claude), Azure OpenAI, AWS Bedrock, Google Vertex AI, and self-hosted models via Ollama and vLLM. Adding a new provider takes minutes — just configure your API key and routing preferences.",
  },
  {
    question: "What compliance standards does OpenProxyAI support?",
    answer:
      "OpenProxyAI is built for regulated environments. We provide immutable audit logs with full request/response history, PII detection and redaction, role-based access controls, and compliance reporting tools for SOC 2, HIPAA, GDPR, and FedRAMP. Our on-premise deployment option ensures your data never leaves your infrastructure.",
  },
  {
    question: "Can I deploy OpenProxyAI on-premise or air-gapped?",
    answer:
      "Yes. OpenProxyAI supports cloud-hosted (SaaS), self-hosted (your cloud), on-premise (your data center), and fully air-gapped deployments. For defense, government, and highly regulated customers, our air-gapped mode runs entirely within your network with zero external dependencies.",
  },
  {
    question: "How does pricing and the free trial work?",
    answer:
      "We offer a 14-day free trial with full Starter-tier access — no credit card required. After the trial, choose from Starter ($2,500/mo for up to 50 users), or Enterprise (custom pricing for unlimited users with on-premise deployment, SLA guarantees, and dedicated support). Annual billing saves approximately 15%.",
  },
]

interface FAQItemProps {
  question: string
  answer: string
  isOpen: boolean
  onToggle: () => void
}

const FAQItem = ({ question, answer, isOpen, onToggle }: FAQItemProps) => {
  const handleClick = (e: React.MouseEvent) => {
    e.preventDefault()
    onToggle()
  }
  return (
    <div
      className={`w-full bg-[rgba(231,236,235,0.08)] shadow-[0px_2px_4px_rgba(0,0,0,0.16)] overflow-hidden rounded-[10px] outline outline-1 outline-border outline-offset-[-1px] transition-all duration-500 ease-out cursor-pointer`}
      onClick={handleClick}
    >
      <div className="w-full px-5 py-[18px] pr-4 flex justify-between items-center gap-5 text-left transition-all duration-300 ease-out">
        <div className="flex-1 text-foreground text-base font-medium leading-6 break-words">{question}</div>
        <div className="flex justify-center items-center">
          <ChevronDown
            className={`w-6 h-6 text-muted-foreground-dark transition-all duration-500 ease-out ${isOpen ? "rotate-180 scale-110" : "rotate-0 scale-100"}`}
          />
        </div>
      </div>
      <div
        className={`overflow-hidden transition-all duration-500 ease-out ${isOpen ? "max-h-[500px] opacity-100" : "max-h-0 opacity-0"}`}
        style={{
          transitionProperty: "max-height, opacity, padding",
          transitionTimingFunction: "cubic-bezier(0.4, 0, 0.2, 1)",
        }}
      >
        <div
          className={`px-5 transition-all duration-500 ease-out ${isOpen ? "pb-[18px] pt-2 translate-y-0" : "pb-0 pt-0 -translate-y-2"}`}
        >
          <div className="text-foreground/80 text-sm font-normal leading-6 break-words">{answer}</div>
        </div>
      </div>
    </div>
  )
}

export function FAQSection() {
  const [openItems, setOpenItems] = useState<Set<number>>(new Set())
  const toggleItem = (index: number) => {
    const newOpenItems = new Set(openItems)
    if (newOpenItems.has(index)) {
      newOpenItems.delete(index)
    } else {
      newOpenItems.add(index)
    }
    setOpenItems(newOpenItems)
  }
  return (
    <section className="w-full pt-[66px] pb-20 md:pb-40 px-5 relative flex flex-col justify-center items-center">
      <div className="w-[300px] h-[500px] absolute top-[150px] left-1/2 -translate-x-1/2 origin-top-left rotate-[-33.39deg] bg-primary/10 blur-[100px] z-0" />
      <div className="self-stretch pt-8 pb-8 md:pt-14 md:pb-14 flex flex-col justify-center items-center gap-2 relative z-10">
        <div className="flex flex-col justify-start items-center gap-4">
          <h2 className="w-full max-w-[435px] text-center text-foreground text-4xl font-semibold leading-10 break-words">
            Frequently Asked Questions
          </h2>
          <p className="self-stretch text-center text-muted-foreground text-sm font-medium leading-[18.20px] break-words">
            Everything you need to know about OpenProxyAI and how it secures your enterprise AI deployment
          </p>
        </div>
      </div>
      <div className="w-full max-w-[600px] pt-0.5 pb-10 flex flex-col justify-start items-start gap-4 relative z-10">
        {faqData.map((faq, index) => (
          <FAQItem key={index} {...faq} isOpen={openItems.has(index)} onToggle={() => toggleItem(index)} />
        ))}
      </div>
    </section>
  )
}
