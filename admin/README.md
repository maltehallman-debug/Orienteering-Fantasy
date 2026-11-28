# Adminpanel · Fantasy Orientering

Ett kontrollcenter för sajten: redigera utseende och texter genom att klicka på element, förhandsgranska som besökare,
spelare eller admin, slå av och på funktioner, kör tester, och spara utkast som du publicerar när du är nöjd.

## Adresser

| Var | Adress |
|---|---|
| GitHub Pages | `https://maltehallman-debug.github.io/Orienteering-Fantasy/admin/` |
| Bredvid sajten (Vercel) | `https://www.fantasyorientering.se/admin/` |

Båda fungerar likadant. Mappen `admin/` publiceras automatiskt med resten av repot: GitHub Pages serverar repots rot från
`main`, och Vercel gör samma sak. Inget extra byggsteg behövs.

## Inloggning och säkerhet

- Du loggar in med ditt vanliga konto (Supabase Auth). Bara konton i tabellen `app_admins` kommer in.
- **Säkerheten ligger i databasen, inte i sidan.** Utkast, versioner och statistik skyddas av row level security och
  funktioner som kontrollerar `public.is_admin()`. Även om någon ändrar i sidans kod kan de inte läsa utkast eller
  publicera.
- Inga hemliga nycklar finns i koden. Supabase-nyckeln i `js/config.js` är den publika nyckeln som sajten redan använder.
- **Demoläge** (utan inloggning) är till för att prova: utkast sparas bara i webbläsaren och inget kan publiceras.

## Så fungerar det

1. **Redigera:** sajten visas i en ram. Klicka på ett element och ändra text, storlek, vikt, typsnitt, färger,
   marginaler, padding, bredd, höjd, hörn, synlighet, länkmål, vilken sida en knapp öppnar, bildadress eller ordning.
   Du kan också lägga till egna sektioner med rubrik, text, bild och knapp.
2. **Förhandsgranska:** samma sida som mobil, surfplatta och dator samtidigt, för valfri vy, med utkastet eller det
   publicerade.
3. **Funktioner och tema:** slå av och på hela delar av sajten, visa ett meddelande överst och justera färger, hörn och
   textstorlekar.
4. **Kommandon:** snabbknappar och en kommandorad (`hjälp` visar allt).
5. **Testläge:** kör sajtens tester i alla vyer och se JavaScript-fel.
6. **Utkast och versioner:** spara, se skillnaden mot det publicerade, publicera med en beskrivning, ångra, återställ
   en tidigare version, exportera eller importera som fil.

Förhandsvisningarna kör sajten med `?sandbox=1&edit=1`. Då använder sajten ett tillfälligt minne i stället för
webbläsarens lagring, loggar inte in någon och sparar ingenting. Inget du testar kan påverka riktiga konton.

## Publicering

- **Spara utkast** lagrar ändringarna i databasen (`site_config.draft`). Inget syns på sajten.
- **Publicera** kopierar utkastet till `site_config.published` och sparar en version i `site_config_history`.
- Sajten läser det publicerade vid varje sidladdning (`get_site_config`) och lägger det över sidan. **Ingen ny
  utläggning hos Vercel behövs**, så det påverkar inte gränsen för antal utlägg.
- **Bygg om sajten** (kommandot `bygg`) startar datauppdateringen och ett nytt utlägg via serverfunktionen `apply-now`.
  Den behövs bara för ny data, inte för ändringar gjorda i adminpanelen.

## Vad som kräver mer än adminpanelen

| Funktion | Läge |
|---|---|
| Antal besökare | Finns i Vercel Analytics. Att visa siffran i panelen kräver en Vercel-nyckel på en server, aldrig i sidan. |
| Sluten beta på/av | Visas på översikten. Ändras i databasen (`app_flags`), eftersom tabellen inte har någon skrivregel för admins. |
| Ändra spelets logik (poäng, priser, regler) | Kräver ändring i källkoden, inte i adminpanelen. |
| Testa riktig inloggning med e-post | Gör det med ett eget testkonto på sajten. Panelens vyer simulerar inloggning utan riktiga konton. |

## Filer

```
admin/
  index.html          skalet
  admin.css           utseendet (ljust och mörkt)
  js/config.js        adresser, flaggor, temavariabler
  js/api.js           Supabase och GitHubs öppna API
  js/store.js         utkast, ångra, spara, publicera, versioner, skillnader
  js/frame.js         förhandsramen och meddelanden till sajten
  js/ui.js            små hjälpfunktioner för gränssnittet
  js/app.js           inloggning, meny, vyer
  js/views/*.js       en fil per vy
supabase/migrations/20261128_site_config.sql   tabeller, regler och funktioner
```

Sajtens sida av det hela finns i `pipeline/build/game.template.html`. Där finns blocket "SITE CONFIGURATION", som läser
och lägger på konfigurationen, och "the bridge to the dashboard", som tar emot meddelanden från panelen.

## Lägga till en ny vy

Skapa `js/views/min-vy.js` med en funktion `minVy(root, shared, go)` som bygger vyn i `root` och returnerar en
städfunktion. Lägg sedan till den i listan `VIEWS` i `js/app.js`.
