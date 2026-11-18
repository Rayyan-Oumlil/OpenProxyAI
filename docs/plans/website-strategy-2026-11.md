# OpenProxyAI: plan de contextualisation du site (web-app)

Date: 2026-11-15. Basé sur l'audit du repo (README, docs/features.md, web-app/src, docs-site) et sur une recherche web. Les sources marquées *vendor* sont des blogs d'éditeurs concurrents: elles indiquent ce que le marché dit, pas des faits indépendants.

---

## 0. En une page

**Le produit est très en avance sur le site.** Le backend a une vraie différence (routage par classe de données sans repli silencieux, MCP gateway avec pinning et taint tracking, RLS, SCIM, plugins WASM, boucle d'évaluation). Le site, lui, vend un « control plane » générique, et 8 de ces différenciateurs n'y apparaissent nulle part (voir §2).

**Les 3 problèmes à régler avant tout le reste:**

| # | Problème | Pourquoi c'est grave |
|---|---|---|
| P0 | Le hero affiche `LIVE · v2.4.1`, `wss://stream` et un flux de requêtes **aléatoires** présenté comme live. Le backend est en `0.1.0`. | Ton acheteur cible est un responsable sécurité. Une fausse métrique « live » détruit la crédibilité d'une page qui vend la **preuve**. |
| P1 | Aucun lien GitHub, aucun SOC 2 ou équivalent, aucune preuve sociale, aucune commande à copier sur la home. | Pour un outil open source, le repo EST la preuve. Et ton meilleur atout (`docker compose ... up`, sans clé, sans coût) est enfoui dans une section Deploy. |
| P2 | Positionnement générique (« control plane for enterprise AI. One gateway. Every model. Every audit. »). | La catégorie est saturée. « Plusieurs providers, une API » est la base que tout le monde affiche. |

**Le positionnement recommandé** (déjà dans ton README, absent du site): *« La passerelle LLM pour les organisations qui doivent prouver ce que leur IA a fait. »*

**L'ordre de travail:** corriger la confiance (P0) → positionnement et copy → architecture de l'information → page pilote → preuve → mouvement (GSAP, etc.) en dernier.

---

## 1. Audit produit: ce qui est construit

Source: [docs/features.md](../features.md) et README. Regroupé en 8 piliers de valeur plutôt que par endpoint.

| Pilier | Capacités clés | Différenciant ? |
|---|---|---|
| **Preuve et audit** | Logs append-only, trace de requête (waterfall), export SIEM (CEF/JSON/syslog), OpenTelemetry `gen_ai.*`, exports de conformité, refus 446 avec explication en langage clair | **Oui, c'est le cœur** |
| **Routage par classe de données** | `public < internal < confidential < secret`, registre de modèles, **aucun repli silencieux**, aperçu de politique sans envoi, résidence des données | **Oui, rare** |
| **MCP gateway** | Pinning d'outils (hash, drift), scan d'injection, grants par rôle/équipe/clé, bundles virtuels, taint tracking | **Oui, très en avance** |
| **Politique et garde-fous** | PII, injection (modèle DeBERTa + regex), garde-fous de réponse, plugins WASM sandboxés, gabarits HIPAA/PCI/FedRAMP-aligned | Partiel |
| **Coûts** | Budgets par org/équipe/utilisateur/modèle, pré-vérification avant streaming, anomalies, showback par label | Standard bien exécuté |
| **Identité et isolation** | RBAC, OIDC, SCIM 2.0 (Okta, Entra), RLS Postgres forcée, SSRF guard sur chaque connexion | Oui pour le segment régulé |
| **Évaluation** | Feedback, datasets, évaluateurs, A/B adaptatif, gate de promotion de prompt | Rare dans une gateway |
| **Exploitation** | Docker Compose, Helm, mode air-gap, Vault/AWS SM, Prometheus, démo à une commande | Standard |

Base de code: 397 commits, ~150 fichiers de tests backend, CI avec axe (WCAG 2.1 AA), smoke test de la démo.

## 2. Audit du site actuel

**Structure:** 5 routes (`/`, `/product`, `/security`, `/providers`, `/pricing`), 18 sections. Docs Docusaurus séparée avec **125 articles de blog** (comparatifs vs LiteLLM, Portkey, Kong, Cloudflare, Helicone, LangChain; EU AI Act; HIPAA; Law 25; MCP).

**Ce que le site mentionne vs ce que le produit fait** (recherche dans `web-app/src`):

| Capacité | Mentionnée sur le site ? |
|---|---|
| Classe de données / routage par classification | **Non** (seulement le mot dans un flux aléatoire du hero) |
| Aperçu de politique (policy preview) | **Non** |
| Tool pinning / taint tracking MCP | **Non** (MCP cité 2 fois, sans détail) |
| SCIM, RLS, plugins WASM | **Non** |
| Évaluation, A/B, gate de prompt | **Non** |
| SIEM / OpenTelemetry | **Non** |
| Lien GitHub / SOC 2 | **Non** |
| Air-gap, Helm/VPC, HIPAA/GDPR/Law 25, audit, Docker | Oui |

**Autres constats:**
- Les noms de modèles du hero (`gpt-4o`, `claude-3.5-sonnet`, `gemini-1.5-pro`) sont datés: ton propre blog parle déjà de Claude Opus 5.5.
- Sur mobile, `RouterSection`, `DeploySection` et `PricingSection` sont masqués: plus de 60 % du trafic landing est mobile selon [une source](https://marketbetter.ai/blog/best-practices-for-landing-page-design/) (*vendor*, à prendre avec prudence).
- Le CTA principal est `$ start trial →` vers `app.openproxyai.com`, alors que le README raconte une histoire self-host/open source. **À clarifier: existe-t-il une offre hébergée ?** (voir §9).
- Pricing: les tiers limitent la rétention d'audit (7/30/90/365 jours) et listent « policy + DLP » dans Business. Or [les acheteurs signalent que RBAC et audit logs sont souvent réservés aux tiers payants chez les concurrents](https://www.requesty.ai/blog/enterprise-ai-gateway) (*vendor*). Vérifier ce qui est réellement bloqué dans le code (`assert_plan_allows`) avant d'écrire la page.

## 3. Recherche: ce que le marché cherche

### 3.1 Ce que les acheteurs entreprise demandent à une gateway LLM
Quatre demandes reviennent dans les guides d'achat 2026 ([Maxim](https://www.getmaxim.ai/bifrost/resources/buyers-guide), [MintMCP](https://www.mintmcp.com/blog/best-llm-gateways), [Requesty](https://www.requesty.ai/blog/enterprise-ai-gateway), [Concentrate](https://concentrate.ai/blog/access-controls-audit-logs-and-zdr-as-enterprise-llm-gateway-selection-criteria); tous *vendor*):

1. **Contrôle des coûts:** budgets par équipe/app/agent, arrêts durs, chargeback. Un guide conseille de tester en POC qu'un dépassement déclenche réellement le blocage.
2. **Contrôle d'accès:** RBAC, SSO/SCIM, allowlists de modèles par équipe, app, environnement et **classe de données**.
3. **Logs de niveau conformité:** par requête (appelant, modèle, tokens, coût, latence, décision de politique), exportables vers un SIEM, avec une durée de rétention claire.
4. **Sécurité de contenu en ligne:** PII, jailbreak, filtres sur streaming et non-streaming.

Plus: déploiement auto-hébergé/VPC pour les régulés, et comportement du failover.

**Lecture pour toi:** tu couvres les quatre. Mais « classe de données » (point 2) est exactement ton différenciant, et c'est un critère que les guides citent déjà. Aucun ne dit que quelqu'un le fait bien.

### 3.2 Le paysage concurrent
([Guptadeepak](https://guptadeepak.com/tools/top-5-ai-gateways-2026/), [Tetrate](https://tetrate.io/learn/ai/best-enterprise-ai-gateway), [Contabo](https://contabo.com/blog/best-llm-gateways/); *vendor*)

| Concurrent | Position perçue | Ton angle |
|---|---|---|
| **LiteLLM** | Le proxy open source le plus répandu, auto-hébergé, orienté développeurs et suivi de coûts | Tu l'utilises comme moteur (100+ providers). Ta valeur est **au-dessus**: gouvernance et preuve. Ne rivalise pas sur le nombre de providers. |
| **Portkey** | Géré, gateway + LLMOps, guardrails, versionnage de prompts, auto-hébergement plus limité | Toi: auto-hébergé d'abord, Apache-2.0, air-gap |
| **Helicone** | Observabilité et analytique de coûts; décrit comme n'**imposant** pas de politique | Toi: tu appliques, pas seulement tu observes |
| **Kong AI Gateway** | Choix par défaut si Kong est déjà en place; lourd pour une équipe 100 % IA | Toi: pas besoin d'une plateforme API entière |

Le fait que les comparatifs aient aussi du bruit non fiable est à garder en tête: une source affirme un rachat de Portkey en mai 2026 et des versions malveillantes de LiteLLM en 2026. **Je n'ai trouvé aucune corroboration. Ne les utilise dans aucun contenu sans les vérifier à la source.**

### 3.3 Ce qui convertit sur une page d'outil développeur
([Evil Martians, 100 landing pages dev tools](https://evilmartians.com/chronicles/we-studied-100-devtool-landing-pages-here-is-what-actually-works-in-2025), [Veza](https://www.vezadigital.com/post/best-devtool-website-design-examples), [DEV](https://dev.to/ninadpathak/the-show-code-rule-why-your-hero-section-is-failing-3oe3))

- **Du vrai code exécutable au-dessus de la ligne de flottaison**, pas une capture d'écran de code.
- **Un chiffre précis plutôt qu'une affirmation.**
- **« Pas de baratin commercial »** et un CTA qui ne prend pas le lecteur de haut: règle citée sur presque toutes les pages étudiées.
- Une valeur claire en 5 secondes, preuve de confiance juste après le hero, tarifs visibles (pas de « contactez-nous »).
- Limite: l'étude date de 2025 et je n'ai pas pu lire ses sections hero/preuve sociale en détail; je n'ai pas trouvé d'étude 2026 spécifique à l'infrastructure open source.

### 3.4 Comment un acheteur sécurité évalue un fournisseur open source
([PostHog trust center](https://trust.posthog.com), [doc LiteLLM conformité](https://docs.litellm.ai/docs/enterprise/compliance), et des guides de revue fournisseur)

- Le point d'entrée est la **page sécurité / trust center**, puis le rapport SOC 2 lui-même (pas le badge), la liste des sous-traitants, et ce qui reste hors audit en self-host.
- **L'auto-hébergement change la question**: l'acheteur peut inspecter le code et les fichiers de déploiement. C'est un argument à exploiter: « vérifie toi-même », avec des affirmations qu'on peut contrôler dans le code (ex.: « aucun repli silencieux », « le gateway ne transmet jamais l'Authorization de l'appelant à un serveur MCP »).
- Sans entité certifiée, une **revue formelle basée sur des informations publiques** est une alternative acceptée (avis d'un consultant, pas d'une norme).

### 3.5 MCP et agents
([CSA, tool poisoning et rug pulls, mai 2026](https://labs.cloudsecurityalliance.org/research-rb/csa-whitepaper-mcp-security-tool-poisoning-20260506-csa-styl/), [Snowflake](https://www.snowflake.com/en/blog/engineering/enterprise-mcp-gateway-ai-agent-governance/), [Composio](https://composio.dev/blog/what-is-mcp-gateway-and-why-your-enterprise-need-it))

- La **menace est documentée**: tool poisoning, rug pulls, injection indirecte, tool squatting. Les acheteurs demandent identité par agent, identifiants à portée limitée, approbation par outil, détection de serveurs fantômes.
- Un guide note que **plusieurs gateways ne disent rien sur la détection de poisoning/injection**: ton pinning avec hash + drift + scan est un vrai argument.
- Limite: la demande côté marché n'est appuyée que par des affirmations d'éditeurs. Un chiffre souvent cité (« 5,5 % des serveurs MCP publics vulnérables ») n'a pas été vérifié contre l'étude d'origine: **ne pas l'utiliser**.

### 3.6 Réglementation (angle d'entrée, pas un slogan)
([FireTail sur l'article 12](https://www.firetail.ai/blog/article-12-and-the-logging-mandate-what-the-eu-ai-act-actually-requires), [DeepInspect](https://www.deepinspect.ai/blog/guides-eu-ai-act-article-12-logging-implementation); *vendor*)

- L'article 12 exige un enregistrement automatique des événements; les déployeurs doivent conserver les logs au moins 6 mois (art. 26(6)).
- **La date est incertaine**: la plupart des sources disent août 2026, une autre cite un report à décembre 2027 (règlement 2026/1744) pour les systèmes Annex III. Ton blog a déjà deux articles sur ce sujet; **aligne le site sur eux et sur le texte officiel**, jamais sur un blog éditeur.
- Aucune source ne dit qu'une gateway **suffit** à satisfaire l'article 12. Formulation honnête: « fournit les journaux qui aident à... », jamais « rend conforme ».
- **Angle local fort:** ton blog couvre la Loi 25 du Québec. Peu de concurrents ont un angle canadien/québécois.

## 4. Positionnement

**Phrase:** « OpenProxyAI est la passerelle LLM pour les organisations qui doivent *prouver* ce que leur IA a fait. Compatible OpenAI: change le `base_url`, garde ton SDK. »

**Trois piliers de preuve** (chacun doit avoir une démo ou du code sur la page):
1. **Chaque requête est contrôlée, routée par classe de données et journalisée.** Pas de repli silencieux.
2. **Les agents et outils MCP sont bornés.** Pinning, scan, grants, taint.
3. **Tu l'héberges, tu le vérifies.** Apache-2.0, VPC, air-gap, une commande pour l'essayer.

**Ce qu'on ne fait pas:** rivaliser sur « 100+ providers » (c'est LiteLLM), prétendre être « conforme » ou « certifié », annoncer des clients qu'on n'a pas.

## 5. Personas et parcours

| Persona | Question | Besoin sur le site | Action cible |
|---|---|---|---|
| **Ingénieur plateforme / IA** (l'évaluateur, c'est lui qui installe) | « Ça marche en 10 minutes ? Quel overhead ? » | Commande à copier, diff `base_url`, schéma, chiffre de latence | Lancer la démo Docker, star le repo |
| **Sécurité / conformité** (le bloqueur) | « Qu'est-ce qui est loggé ? Où va la donnée ? Qu'est-ce qui est prouvé ? » | Page sécurité, modèle de menace, échantillon d'audit, matrice de contrôles | Lire le doc sécurité, demander une revue |
| **Responsable (VP/CTO/FinOps)** | « Combien ça coûte ? Que risque-t-on sans ? » | Prix visibles, exemple de budget, comparatif build vs buy | Prendre un appel |

Le parcours réel est **ingénieur d'abord** (il adopte), puis sécurité (elle valide), puis le responsable (il signe). Le site doit servir le premier sans perdre les deux autres.

## 6. Architecture de l'information

| Page | État | Rôle |
|---|---|---|
| `/` Accueil | À refaire | Convaincre l'ingénieur, rassurer en 30 s |
| `/product` | À restructurer | Les 3 piliers, une section par pilier avec démo |
| `/security` | **À renforcer en priorité** | La page que lit le responsable sécurité |
| `/pricing` | Garder, clarifier | Ce qui est réellement gratuit/payant |
| `/providers` | Sous-page de `/product` ou lien docs | Utile, pas stratégique |
| `/compare` (hub) | **Nouveau** | Tu as déjà 6 comparatifs en blog; une page hub capte l'intention « alternative à X » |
| `/use-cases` ou `/solutions` | Nouveau, plus tard | Santé, finance, public, par équipe |
| Docs et blog | Existants | Garder séparés; relier depuis la home |

## 7. Plan de la page d'accueil

1. **Hero.** Titre du §4. Sous-titre en une phrase. **Bloc de code réel**: `docker compose -f docker-compose.demo.yml up --build` et le diff de 3 lignes `base_url`. CTA 1: « Essayer en une commande ». CTA 2: « Voir le repo » (avec les stars quand elles existent). À droite: **une vraie capture ou un enregistrement de ta console de démo**, pas un flux aléatoire.
2. **Bande de confiance.** Apache-2.0 · tests/CI · axe WCAG AA · air-gap · lien vers `/security`. Pas de logos clients inventés.
3. **Le problème en une phrase** + « ce que ça change » (3 colonnes: sans gateway / avec).
4. **Pilier 1: preuve et routage.** Montre une requête bloquée avec le message 446 en langage clair, et l'aperçu de politique. C'est ton moment « wow » le plus concret.
5. **Pilier 2: MCP.** Un outil dont la description change (drift) et qui est bloqué.
6. **Pilier 3: déploiement.** VPC / Helm / air-gap, une commande.
7. **Preuves chiffrées.** Overhead mesuré (ton article « four milliseconds »), nombre de tests, rétention.
8. **Comparaison honnête** (lien `/compare`).
9. **Tarifs** en bref, FAQ courte.
10. **CTA final** + pied de page avec GitHub, docs, sécurité.

Règle: chaque section répond à une question précise d'un persona. Si elle n'en a pas, on la supprime.

## 8. Preuve sans clients

Tu n'as pas de logos. C'est normal à ce stade; l'honnêteté est un avantage ici.

- **Vérifiable:** démo à une commande, repo public, tests, CI, rapport d'accessibilité.
- **Mesuré:** latence ajoutée (avec méthode et matériel), pas d'adjectifs.
- **Écrit:** modèle de menace, ce que la gateway **ne fait pas** (« pas une autorisation FedRAMP », déjà écrit dans ta doc), limites connues. Les acheteurs sécurité y croient plus qu'aux promesses.
- **Interdit:** métriques « live » factices, logos non autorisés, « conforme à », « certifié ».

## 9. Décisions dont j'ai besoin

1. **Existe-t-il une offre hébergée** (`app.openproxyai.com`) ou le produit est-il auto-hébergé uniquement? Le CTA « start trial » en dépend.
2. **Qui est la cible n°1**: équipes régulées canadiennes/québécoises (angle Loi 25, ta niche) ou marché international?
3. **Que fait réellement le plan Community par rapport aux plans payants?** Vérifier dans le code avant d'écrire la page tarifs.
4. **Quel objectif de conversion**: stars GitHub, démos lancées, appels (Calendly)? Un seul objectif principal.
5. **As-tu une mesure de latence reproductible** (l'article « four milliseconds »)? Si oui, on l'affiche.

## 10. Phasage

| Phase | Contenu | Critère de réussite |
|---|---|---|
| **A. Confiance** (1 à 2 h) | Retirer `LIVE · v2.4.1`, `wss://stream` et le faux flux, ou l'étiqueter « exemple simulé ». Ajouter le lien GitHub partout. Mettre à jour les noms de modèles. | Plus aucune affirmation fausse sur la home |
| **B. Positionnement et copy** | Nouveau titre, 3 piliers, textes de chaque section | Un lecteur résume le produit en une phrase après 10 s |
| **C. IA et page pilote** | Structure du §6, home refaite en code, mobile complet | Home validée dans le navigateur, y compris sur téléphone |
| **D. Sécurité et preuve** | Page `/security` renforcée, `/compare`, chiffres de latence | Un responsable sécurité trouve ses réponses sans parler à personne |
| **E. Design system** | Typo, espace, tokens; déclinaison sur les autres pages | Cohérence sur les 5 pages |
| **F. Mouvement** | 1 animation GSAP signature (le trajet d'une requête), 2 ou 3 accents React Bits | Lighthouse inchangé ou meilleur; `prefers-reduced-motion` respecté |
| **G. Mesure** | Analytics (conversion, scroll, clics CTA) | On sait quelle section convertit |

La phase A peut se faire **avant même de choisir un design**. Elle est la plus rentable.

## 11. Risques

- **Sur-vendre la conformité.** Utiliser « aide à documenter », pas « garantit ».
- **Dérive de la copy vs le produit.** Une affirmation sur le site doit pointer vers un fichier du repo ou un test. Je propose de garder un tableau « affirmation → preuve » dans ce dossier.
- **Fiabilité de la recherche.** La plupart des sources sont des blogs d'éditeurs. Les tendances (les 4 besoins, la menace MCP) sont cohérentes entre sources; les chiffres isolés ne le sont pas et sont exclus.
- **SEO et animation.** Le site est pré-rendu: tout contenu doit être présent dans le HTML sans JavaScript.

---

## 12. Exécution (2026-11-16)

Phases A à G exécutées dans `web-app/`. Décisions prises par défaut, sur la base du code (à contredire si faux):

| # | Question | Décision | Preuve |
|---|---|---|---|
| 1 | Offre hébergée ? | **Non.** Auto-hébergé uniquement. | `app.openproxyai.com` et `api.openproxy.ai` ne résolvent pas (DNS); le trust center dit « self-hosted ». Le CTA « start trial » est retiré. |
| 2 | Cible n°1 | Équipes régulées (santé, finance, public). Loi 25 et AI Act en liens vers le blog, sans dates. | Blog existant. |
| 3 | Ce que bloque Community | 3 utilisateurs, 5 clés, 7 j de rétention, pas de réglage PII/gabarits de conformité, pas de SSO/SCIM. Rien d'autre n'est bloqué par plan. | `PLAN_FEATURES` dans `backend/app/config.py`; `assert_plan_allows` appelé seulement pour `pii_detection` et `sso_enabled`. |
| 4 | Objectif de conversion | Lancer la démo (une commande). Secondaire: étoile GitHub. Calendly seulement pour les plans payants. | — |
| 5 | Mesure de latence | **Aucune mesure reproductible.** Tous les chiffres de latence retirés (« four milliseconds », budget p50, latences de cache). | Le post `four-milliseconds` ne contient aucun chiffre. |

Autres retraits car faux ou invérifiables: `curl openproxy.ai/install.sh` (le serveur coupe la connexion), `api.openproxy.ai` (ne résout pas), chip « terraform » (rien dans `deploy/`), « SAML » (le backend ne supporte que OIDC), noms de métriques Prometheus inventés (remplacés par les vrais de `metrics_service.py`), trafic et débits fictifs de RouterSection, durées « build vs buy ».

Phase F: une animation GSAP (trajet d'une requête, une passe sur deux refusée en 446), chargée à la demande, désactivée avec `prefers-reduced-motion`. Pas de Lenis, pas de React Bits.
Phase G: événements `data-track` + `section_view` via `@vercel/analytics`. Les événements personnalisés exigent un plan Vercel qui les inclut; sans eux, seules les pages vues sont comptées.

À savoir: la démo exige les ports 8000 et 5173 libres (la console appelle l'API en dur sur localhost:8000). Un autre conteneur sur 8000 la fait échouer.
