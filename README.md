# Boligvarsler for København

En liten robot som følger med på utleieboliger i København og sender deg et
**Telegram-varsel** så snart en ny bolig som passer kriteriene dine dukker opp.

Boten **søker aldri og kontakter aldri utleier** – den bare finner og varsler.
Hvert varsel følges av et forslag til søknadstekst (i en egen melding) som du
selv kan kopiere, lese gjennom og sende hvis du vil.

---

## Innhold
1. [Hva den overvåker](#hva-den-overvåker)
2. [Slik virker det (kort)](#slik-virker-det-kort)
3. [Kom i gang – Telegram](#kom-i-gang--telegram)
4. [Kjøre lokalt på Mac](#kjøre-lokalt-på-mac)
5. [Kjøre i skyen (GitHub Actions – anbefalt)](#kjøre-i-skyen-github-actions--anbefalt)
6. [Endre kriterier (m², rom, pris, områder)](#endre-kriterier)
7. [Lokal kjøring hver time (launchd)](#lokal-kjøring-hver-time-launchd)
8. [Se logger / feilsøking](#se-logger--feilsøking)
9. [Status per nettside](#status-per-nettside)

---

## Hva den overvåker

| Nettside       | Status        | Datakilde |
|----------------|---------------|-----------|
| **BoligPortal** | ✅ Aktiv | Server-rendret JSON (SearchResultApp), nyeste først |
| **Lejebolig** | ✅ Aktiv | Server-rendret HTML pr. bydel, «Nyeste øverst» |
| **Boligsiden** (kun leie) | ✅ Aktiv | Offentlig JSON-API |
| **City Apartment** | ✅ Aktiv | WordPress REST + detaljside |
| **Heimstaden** | ✅ Aktiv | HTML-oversiktsside (alle boliger inline) |
| CEJ            | ⏸️ Stub | SPA/API med rate-limit – ikke ferdig |
| CDC            | ⏸️ Stub | Domene ikke bekreftet |
| Findbolig      | ⏸️ Stub | Krever medlemskap/ansiennitet – bruk deres egen e-postagent |

De aktive kildene dekker det store flertallet av private utleieboliger i
København – **BoligPortal** og **Lejebolig** er de to største portalene og
samler annonser fra svært mange utleiere. De tre siste er trygge «stubs» som
returnerer tomt uten å feile – se
[Status per nettside](#status-per-nettside) for begrunnelse.

---

## Slik virker det (kort)

1. Hvert 10. minutt hentes alle ledige boliger fra de aktive kildene.
2. De filtreres på kriteriene i `config.yaml` (størrelse, antall rom, maks
   leie, områder via postnummer).
3. Boliger som mangler m²/rom/pris blir **ikke** forkastet – de sendes med
   markeringen «⚠️ mangler data» så du selv kan vurdere.
4. Nye treff (som ikke er sett før) sendes til Telegram, hvert med en
   søknadstekst i en egen melding.
5. **Første kjøring** registrerer alt som finnes akkurat nå *uten* å varsle –
   du får bare én kort oppsummering. Slik unngår du 50 varsler på én gang.
   Deretter varsles kun det som er genuint nytt.

Hvilke boliger som er sett før lagres i `data/seen.json`. I skyen committes
denne filen tilbake til repoet etter hver kjøring, så listen overlever.

---

## Kom i gang – Telegram

Du trenger to ting: en **bot-token** og din **chat-ID**.

### 1. Opprett boten (bot-token)
1. Åpne Telegram og søk opp **@BotFather**.
2. Send `/newbot`, følg instruksjonene (gi boten et navn og et brukernavn
   som slutter på `bot`).
3. BotFather svarer med en token, f.eks. `123456789:AAH...`. **Kopiér den.**

### 2. Finn chat-ID-en din
1. Søk opp din nye bot i Telegram og trykk **Start** (send en melding, f.eks. «hei»).
2. Søk opp **@userinfobot** i Telegram og send `/start` – den svarer med
   `Id: 123456789`. Det tallet er din chat-ID.
   - Alternativt: åpne
     `https://api.telegram.org/bot<DIN-TOKEN>/getUpdates` i nettleseren etter
     at du har sendt en melding til boten, og les `chat.id` i svaret.

### 3. Legg verdiene inn
- **Lokalt:** kopiér `.env.example` til `.env` og fyll inn verdiene.
- **I skyen:** legg dem inn som *Secrets* i GitHub (se under).

---

## Kjøre lokalt på Mac

```bash
# 1. Lag et virtuelt miljø og installer avhengigheter
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 2. Sett opp hemmeligheter
cp .env.example .env
#   Åpne .env og fyll inn TELEGRAM_BOT_TOKEN og TELEGRAM_CHAT_ID

# 3. Testkjør ALT én gang – henter og printer funn, sender INGEN varsler
.venv/bin/python main.py --test

# 4. Ekte kjøring (sender varsler til Telegram)
.venv/bin/python main.py
```

`--test` er trygt å kjøre så ofte du vil: den lagrer ingenting og sender
ingen meldinger – den bare viser hva som finnes og hva som matcher.

Legg til `-v` for mer detaljert (debug) logging.

---

## Kjøre i skyen (GitHub Actions – anbefalt)

Da kjører boten hvert 10. minutt **uten at Mac-en din er på**.

### 1. Lag et repo
Opprett et nytt repo på GitHub og last opp denne mappen:

```bash
git init
git add .
git commit -m "Boligvarsler"
git branch -M main
git remote add origin git@github.com:<ditt-brukernavn>/<repo-navn>.git
git push -u origin main
```

> `.env` lastes **ikke** opp – den ligger i `.gitignore`. All kontaktinfo og
> søknadsteksten legges i stedet inn som GitHub *Secrets* (neste steg), aldri i
> koden. Derfor er det trygt å gjøre repoet **offentlig** – og offentlige repo
> har ubegrensede gratis Actions-minutter, som er det som gjør 10-min-kadensen
> gratis. (Gjør du det offentlig: pass på at git-historikken er ren for
> persondata – start gjerne et ferskt repo uten gammel historikk.)

### 2. Legg inn Secrets
Gå til repoet på github.com → **Settings** → **Secrets and variables** →
**Actions** → **New repository secret**, og legg inn disse:

| Navn | Verdi |
|------|-------|
| `TELEGRAM_BOT_TOKEN` | token fra BotFather |
| `TELEGRAM_CHAT_ID`   | din chat-ID |
| `KONTAKT_NAVN`       | ditt navn |
| `KONTAKT_TLF`        | ditt telefonnummer |
| `KONTAKT_ADRESSE`    | din adresse |
| `SOKNAD_TEKST`       | (valgfri) din personlige søknadstekst – bruk `\n` for linjeskift |

> Kontaktinfo og søknadstekst ligger som **Secrets**, aldri i koden – så det er
> trygt selv om repoet er offentlig. Setter du ikke `SOKNAD_TEKST`, brukes den
> generiske `soknad.txt`.

### 3. Slå på og test
- Workflowen (`.github/workflows/boligvarsler.yml`) kjører automatisk
  **hvert 10. minutt**. (Offentlig repo = ubegrensede gratis Actions-minutter,
  så den hyppige kadensen koster ingenting.)
- Du kan også starte den manuelt: fanen **Actions** → **Boligvarsler** →
  **Run workflow**. Bruk dette til å teste at Telegram virker.
- Første kjøring sender bare én oppsummering (ingen boligvarsler) – det er
  meningen. Fra kjøring to og utover får du ekte varsler.

Workflowen trenger skrivetilgang for å kunne lagre `data/seen.json` tilbake.
Det er allerede satt (`permissions: contents: write`). Hvis push skulle
feile, sjekk **Settings → Actions → General → Workflow permissions** og velg
«Read and write permissions».

---

## Endre kriterier

Alt styres fra **`config.yaml`** – ingen koding nødvendig. Lagre filen og
kjør på nytt (eller push til GitHub).

```yaml
kriterier:
  min_m2: 50              # minste størrelse i m²
  min_vaerelser: 2        # minste antall rom
  maks_husleje: 16000     # maks leie i kr./md.
  medregn_aconto_i_filter: true   # true = filtrér på leie + aconto
```

**Områder** styres via postnummer (med bydelsnavn som reserve hvis postnummer
mangler):

```yaml
omraader:
  - navn: "Østerbro"
    postnr: [[2100, 2100]]
    navne: ["Østerbro", "København Ø"]
```

Legg til/fjern områder ved å redigere listen. `postnr` er en liste av
`[fra, til]`-intervaller.

**Slå kilder av/på:**

```yaml
kilder:
  boligportal: true
  lejebolig: true
  heimstaden: true
  cityapartment: true
  boligsiden: true
  cej: false        # f.eks. slå av en stub
```

---

## Lokal kjøring hver time (launchd)

Vil du heller kjøre på egen Mac i stedet for i skyen? Da kan du bruke `launchd`
(Mac-en må være våken og på nett når den skal kjøre).

Fila `deploy/com.boligvarsler.plist` er en ferdig mal. Rett stiene i den til
din egen mappe, så:

```bash
cp deploy/com.boligvarsler.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.boligvarsler.plist
launchctl start com.boligvarsler        # kjør én gang nå for å teste
tail -f boligvarsler.log                # se loggen
```

Stoppe igjen:

```bash
launchctl unload ~/Library/LaunchAgents/com.boligvarsler.plist
```

> Bruk **enten** GitHub Actions **eller** launchd – ikke begge samtidig, ellers
> deler de ikke samme `seen.json` og du kan få dobbeltvarsler.

---

## Se logger / feilsøking

- **Lokalt:** meldinger skrives til terminalen. Kjør med `-v` for debug.
  launchd-kjøringer logges til `boligvarsler.log`.
- **GitHub Actions:** fanen **Actions** → velg en kjøring → se trinnet
  «Kjør boligvarsleren» for full logg.
- **Ingen varsler?** Kjør `python main.py --test` og se om boliger hentes og
  matcher. Hvis «Hentet pr. kilde» viser 0 for en aktiv kilde, kan nettsiden
  ha endret layout.
- **Scraper feiler gjentatte ganger:** etter `fejl_graense` (standard 3)
  feilede kjøringer på rad sender boten deg et eget Telegram-varsel om det.
  Én kildes feil stopper aldri de andre.

---

## Boligsiden + BoligPortal i skyen (viktig)

Både **Boligsiden** og **BoligPortal** sitter bak Cloudflare, som blokkerer
**datacenter-IP-er** (bl.a. GitHub sine servere) med feilkode 403 – uansett hva
vi gjør med forespørselen. Det betyr:

- **Lokalt på Mac-en din:** begge virker perfekt (vanlig bolig-IP).
- **I GitHub Actions (skyen):** begge hopper pent over og henter 0 (de gir
  *ikke* feilvarsler). **Lejebolig, Heimstaden og City Apartment virker som
  normalt i skyen** – så du får fortsatt masse boliger uten noe ekstra.

**Vil du også ha Boligsiden og BoligPortal i skyen?** Legg til én gratis nøkkel
fra Jina AI, så rutes begge kallene gjennom deres relay (som har en
ikke-blokkert IP). Den ene nøkkelen låser opp *begge* sidene:

1. Gå til **https://jina.ai/reader** → logg inn (gratis, Google/e-post) → kopiér
   API-nøkkelen din (starter med `jina_...`).
2. I GitHub-repoet: **Settings → Secrets and variables → Actions → New repository
   secret**:
   - Navn: `JINA_API_KEY`
   - Verdi: nøkkelen din
3. Ferdig. Neste kjøring tar Boligsiden + BoligPortal med automatisk – ingen
   kodeendring.

> Uten denne nøkkelen fungerer alt fint, du går bare glipp av Boligsiden- og
> BoligPortal-boliger i de skybaserte kjøringene (du får dem fortsatt hvis du
> kjører lokalt). BoligPortal er stor, så en Jina-nøkkel anbefales.

---

## Status per nettside

**Aktive (verifisert mot ekte side):**
- **BoligPortal** – Danmarks største leieportal. Søkeresultatet ligger som
  innbygd JSON i siden (`SearchResultApp`). Vi henter København-området
  (som dekker alle ønskede bydeler, inkl. Frederiksberg) sortert med nyeste
  først, så nye annonser alltid ligger øverst – da trenger vi ikke skanne alle
  ~1000 annonser hver gang. Postnummer-filteret skjærer ned til bydelene dine.
- **Lejebolig** – stor leieportal. Vi henter én side pr. bydel (København K,
  Vesterbro, Nørrebro, Østerbro, Frederiksberg) med standard-sortering «Nyeste
  øverst». Bydelen er kjent fra URL-en, så områdematch er presis selv om
  listen ikke viser postnummer.
- **Boligsiden** – offentlig JSON-API, kun leieboliger. Henter København +
  Frederiksberg kommune og filtrerer på postnummer lokalt.
- **City Apartment** – WordPress REST gir adresse + lenke; detaljene (m²,
  pris, postnummer) hentes fra hver boligs detaljside.
- **Heimstaden** – oversiktssiden viser alle ~250 ledige boliger direkte i
  HTML. Postnummer leses fra lenken, resten fra kortteksten.

**Stubs (ikke aktive – returnerer tomt uten å feile):**
- **CEJ** – nettsiden er en enkeltside-app som henter data fra et API med
  rate-limit (429 ved for hyppige kall). Krever uttrekk av API-nøkkel fra
  JavaScript-bunten og forsiktig polling – ikke ferdigstilt.
- **Findbolig** – almene boliger som krever medlemskap og ansiennitet på
  venteliste for i det hele tatt å være aktuelle, og serveren har en ufullstendig
  SSL-kjede. **Anbefaling:** bruk Findboligs egen gratis e-post-søkeagent i
  stedet – den treffer det samme uten teknisk styr.
- **CDC** – domenet lot seg ikke bekrefte entydig. Må kartlegges før det kan
  aktiveres. Slå det eventuelt av i `config.yaml`.

Du kan trygt la stubs stå på (`true`) – de logger bare at de ikke er aktive og
returnerer 0 boliger.
