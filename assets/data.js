/* ==========================================================================
   Case Analytica — content data
   ==========================================================================
   HOW TO ADD A NEW VIDEO
   1. Copy one of the objects in VIDEOS below.
   2. Fill in title, category ("System" | "Restorative Justice" | "Rights & Process" | "Political / News"),
      format ("Short" | "Long-form"), and description.
   3. Once it's live on YouTube, paste the video ID into youtubeId
      (the part after "v=" in the URL, e.g. youtube.com/watch?v=XXXXXXXXXXX)
      and set published to true.
   4. Save this file. That's the entire publishing step — no rebuild needed.

   HOW TO ADD A NEW ARTICLE
   1. Duplicate articles/template.html, rename it to a short-slug.html
      (e.g. articles/bail-reform-explained.html), fill in the content.
   2. Add one entry to ARTICLES below with a matching "slug" (no .html, no spaces).
   3. Save. The articles page will pick it up automatically.
   ========================================================================== */

const VIDEOS = [
  {
    title: "Can NY Police Search Your Phone Without a Warrant?",
    category: "Rights & Process",
    format: "Short",
    description: "Riley v. California settled it in 2014 — here's what that actually means at a traffic stop.",
    youtubeId: "H6cLZtvvHSg",
    published: true
  },
  {
    title: "NY's Clean Slate Act Explained: When Does YOUR Record Actually Seal?",
    category: "System",
    format: "Short",
    description: "Automatic sealing started in November 2024 — the waiting periods and exclusions that decide if you qualify.",
    youtubeId: "",
    published: false
  },
  {
    title: "Restorative Justice vs. Prison: What's the Real Difference?",
    category: "Restorative Justice",
    format: "Short",
    description: "Prison asks how long. Restorative justice asks who was harmed and what they need.",
    youtubeId: "",
    published: false
  },
  {
    title: "What Actually Happens After an Arrest in New York State (Step-by-Step Guide)",
    category: "Rights & Process",
    format: "Long-form",
    description: "From arrest and booking through arraignment, discovery, and sentencing — the full process in plain language.",
    youtubeId: "",
    published: false
  },
  {
    title: "Public Defender vs. Private Attorney in NY: What Actually Matters",
    category: "System",
    format: "Short",
    description: "It's not 'public defender = worse lawyer.' Here's the real difference.",
    youtubeId: "",
    published: false
  },
  {
    title: "How Restorative Justice Diversion Programs Work in NY Courts",
    category: "Restorative Justice",
    format: "Short",
    description: "How a case gets paused or resolved outside standard prosecution — and why it varies by county.",
    youtubeId: "",
    published: false
  },
  {
    title: "3 Things to Say (and 3 to Never Say) at a NY Parole Hearing",
    category: "Rights & Process",
    format: "Short",
    description: "The Board is asking one question: is this person safe to release. What that means for what you say.",
    youtubeId: "",
    published: false
  },
  {
    title: "How to Prepare for a Parole Hearing in New York State (Full Guide)",
    category: "Rights & Process",
    format: "Long-form",
    description: "What the Board evaluates, how to build a release plan, and what to say in the room.",
    youtubeId: "",
    published: false
  },
  {
    title: "If ICE Detains Someone in New York, Do This First",
    category: "Political / News",
    format: "Short",
    description: "Immigration detention runs on different rules than a criminal arrest — including a free NY-funded legal resource.",
    youtubeId: "",
    published: false
  },
  {
    title: "What Is \"Raise the Age\" in New York — And Why It Matters for Teen Arrests",
    category: "System",
    format: "Short",
    description: "Why most 16 and 17 year olds no longer go straight into adult criminal court.",
    youtubeId: "",
    published: false
  },
  {
    title: "How to Support a Loved One Incarcerated in NY (Visits, Mail, Commissary Explained)",
    category: "Rights & Process",
    format: "Short",
    description: "The practical rules nobody hands you a manual for.",
    youtubeId: "",
    published: false
  },
  {
    title: "Restorative Justice in New York: The Real Alternatives to Incarceration",
    category: "Restorative Justice",
    format: "Long-form",
    description: "Beyond 'lock them up' or 'let them off easy' — the actual mechanisms running in NY courtrooms right now.",
    youtubeId: "",
    published: false
  }
];

const ARTICLES = [
  {
    slug: "just-arrested-what-youre-facing",
    title: "You've Just Been Arrested in New York: What You're Actually Facing, and the Question That Changes Everything",
    category: "Restorative Justice",
    date: "2026-07-26",
    excerpt: "What the first hours and days after an arrest actually look like, and the one question about restorative justice that has to be asked before a plea — not after."
  },
  {
    slug: "after-an-arrest-in-new-york",
    title: "What Actually Happens After an Arrest in New York State",
    category: "Rights & Process",
    date: "2026-07-19",
    excerpt: "From the moment of arrest to arraignment, discovery, and sentencing — the full process explained in plain language, so you're not learning these terms for the first time in a courtroom hallway."
  },
  {
    slug: "clean-slate-act-explained",
    title: "The Clean Slate Act: When Does Your NY Record Actually Get Sealed?",
    category: "System",
    date: "2026-07-19",
    excerpt: "New York began automatically sealing eligible criminal records in November 2024. Here's the real timeline, the exclusions, and how to find out where your specific record stands."
  },
  {
    slug: "restorative-justice-alternatives",
    title: "Restorative Justice in New York: The Real Alternatives to Incarceration",
    category: "Restorative Justice",
    date: "2026-07-19",
    excerpt: "Beyond the two-camp framing of 'lock them up' or 'let them off easy' — victim-offender dialogue, diversion programs, and community-based alternatives actually running in New York right now."
  }
];
