/* ==========================================================================
   Case Analytica: content data
   ==========================================================================
   HOW TO ADD A NEW VIDEO
   1. Copy one of the objects in VIDEOS below.
   2. Fill in title, category ("System" | "Restorative Justice" | "Rights & Process" | "Political / News"),
      format ("Short" | "Long-form"), and description.
   3. Once it's live on YouTube, paste the video ID into youtubeId
      (the part after "v=" in the URL, e.g. youtube.com/watch?v=XXXXXXXXXXX)
      and set published to true.
   4. Save this file. That's the entire publishing step. No rebuild needed.

   HOW TO ADD A NEW ARTICLE
   1. Duplicate articles/template.html, rename it to a short-slug.html
      (e.g. articles/bail-reform-explained.html), fill in the content.
   2. Add one entry to ARTICLES below with a matching "slug" (no .html, no spaces).
   3. Save. The articles page will pick it up automatically.
   ========================================================================== */

const VIDEOS = [
  {
    title: "The Bet Every Plea Deal Is Making",
    category: "Restorative Justice",
    format: "Short",
    description: "A plea offer is priced on a guess about what you won't do. Here's the bet baked into every deal, and the question that tells you if it's a safe one.",
    youtubeId: "",
    published: false
  },
  {
    title: "The Question Before You Plead Guilty",
    category: "Restorative Justice",
    format: "Short",
    description: "Almost every criminal case ends in a guilty plea, not a trial. Here's the question that can change that outcome.",
    youtubeId: "ed8sOleYkAE",
    published: true
  },
  {
    title: "Can NY Police Search Your Phone Without a Warrant?",
    category: "Rights & Process",
    format: "Short",
    description: "Riley v. California settled it in 2014: here's what that actually means at a traffic stop.",
    youtubeId: "H6cLZtvvHSg",
    published: true
  },
  {
    title: "NY's Clean Slate Act Explained: When Does YOUR Record Actually Seal?",
    category: "System",
    format: "Short",
    description: "Automatic sealing started in November 2024: the waiting periods and exclusions that decide if you qualify.",
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
    description: "From arrest and booking through arraignment, discovery, and sentencing: the full process in plain language.",
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
    description: "How a case gets paused or resolved outside standard prosecution, and why it varies by county.",
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
    description: "Immigration detention runs on different rules than a criminal arrest, including a free NY-funded legal resource.",
    youtubeId: "",
    published: false
  },
  {
    title: "What Is \"Raise the Age\" in New York: And Why It Matters for Teen Arrests",
    category: "System",
    format: "Short",
    description: "Why most 16 and 17 year olds no longer go straight into adult criminal court.",
    youtubeId: "",
    published: false
  },
  {
    title: "The Certificate Most People Never Ask For After a NY Conviction",
    category: "System",
    format: "Short",
    description: "A conviction can keep blocking jobs and licenses long after the sentence is over. Here's the Certificate of Relief from Disabilities, and why it has to be requested at sentencing.",
    youtubeId: "",
    published: false
  },
  {
    title: "Order of Protection in New York: What It Actually Restricts (Know Before You Break It)",
    category: "Rights & Process",
    format: "Short",
    description: "A criminal court order of protection isn't the same thing as a Family Court order, and violating it is its own separate crime.",
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
    description: "Beyond 'lock them up' or 'let them off easy': the actual mechanisms running in NY courtrooms right now.",
    youtubeId: "",
    published: false
  }
];

const ARTICLES = [
  {
    slug: "youthful-offender-status-vs-raise-the-age-ny",
    title: "Youthful Offender Status vs. Raise the Age in New York: They're Not the Same Thing",
    category: "System",
    date: "2026-07-31",
    excerpt: "Raise the Age decides which court hears a teenager's case. Youthful Offender status under CPL Article 720 decides what happens to the record afterward. Confusing the two costs people a sealed record they were entitled to ask for."
  },
  {
    slug: "judicial-diversion-program-ny-felony-drug-cases",
    title: "What Is Judicial Diversion in New York? Felony Drug Cases and CPL Article 216",
    category: "Restorative Justice",
    date: "2026-07-31",
    excerpt: "Judicial diversion under CPL Article 216 lets a judge send an eligible felony drug defendant to treatment instead of prison, even over a prosecutor's objection. Here's who qualifies and the exact question to ask."
  },
  {
    slug: "certificate-of-relief-from-disabilities-ny",
    title: "Certificate of Relief from Disabilities in New York: How to Get Your Rights Back After a Conviction",
    category: "Access to Justice",
    date: "2026-07-31",
    excerpt: "A conviction can block a job, a license, even housing, long after the sentence is served. A Certificate of Relief from Disabilities doesn't erase the conviction. It removes the legal barrier anyway. Here's who qualifies and how to ask for one."
  },
  {
    slug: "order-of-protection-criminal-court-ny",
    title: "How a Criminal Court Order of Protection Actually Works in New York",
    category: "Rights & Process",
    date: "2026-07-31",
    excerpt: "An order of protection issued in a criminal case isn't the same thing as one from Family Court, and violating it is its own separate crime. Here's how it gets issued, how long it lasts, and what happens if it's broken."
  },
  {
    slug: "what-is-an-acd-in-new-york",
    title: "What Is an ACD in New York? Adjournment in Contemplation of Dismissal, Explained",
    category: "Restorative Justice",
    date: "2026-07-30",
    excerpt: "An ACD isn't a diversion program by name, but it works like one: complete a clean adjournment period and the case is dismissed and sealed. Here's when it applies and why it's not automatic."
  },
  {
    slug: "pleading-guilty-immigration-consequences-ny",
    title: "Will Pleading Guilty Affect Your Immigration Status in New York?",
    category: "Rights & Process",
    date: "2026-07-30",
    excerpt: "New York law requires a judge to read a warning about deportation before a felony plea. It's a formality, not an explanation. Here's what that warning actually means."
  },
  {
    slug: "cost-of-a-criminal-defense-lawyer-ny",
    title: "How Much Does a Criminal Defense Lawyer Actually Cost in New York?",
    category: "Access to Justice",
    date: "2026-07-30",
    excerpt: "Retainers, flat fees, hourly rates: what actually drives the price of private counsel in New York, and where that leaves you if a full-time attorney isn't in the budget."
  },
  {
    slug: "how-bail-works-in-ny-after-reform",
    title: "How Bail Actually Gets Set in New York After Bail Reform",
    category: "System",
    date: "2026-07-30",
    excerpt: "Bail reform didn't eliminate cash bail, it narrowed it. What changed in 2019, what got added back in 2020 and 2022, and the question to ask about why bail was set the way it was."
  },
  {
    slug: "does-a-conviction-show-on-background-check-ny",
    title: "Does a Conviction Actually Show Up on a Background Check in New York?",
    category: "System",
    date: "2026-07-30",
    excerpt: "The direct answer, and how it connects to the Clean Slate Act's sealing timeline, so a job application doesn't feel like a second sentence."
  },
  {
    slug: "quick-answers-just-arrested-ny",
    title: "Quick Answers: Just Been Arrested in New York (FAQ)",
    category: "Rights & Process",
    date: "2026-07-30",
    excerpt: "Direct answers to the questions people actually search in the first hours after an arrest, each linked to the full explanation."
  },
  {
    slug: "the-bet-every-plea-deal-is-making",
    title: "The Bet Every Plea Deal Is Making",
    category: "Restorative Justice",
    date: "2026-07-30",
    excerpt: "A plea offer isn't a neutral number. It's a bet that you and your attorney won't take the case to trial. Here's how to tell if that bet is a safe one."
  },
  {
    slug: "the-question-before-you-plead-guilty",
    title: "The Question Before You Plead Guilty",
    category: "Restorative Justice",
    date: "2026-07-29",
    excerpt: "Almost every criminal case ends in a guilty plea, not a trial. Here's the pressure that drives that, and the one question that can change the outcome."
  },
  {
    slug: "two-failures-after-a-nys-arrest",
    title: "The Two Failures Nobody Warns You About: Information and Representation After a NY Arrest",
    category: "Access to Justice",
    date: "2026-07-27",
    excerpt: "Two things break down at almost the same moment after a New York arrest: nobody explains what's happening, and nobody guarantees someone with the time to fight for you. Start here."
  },
  {
    slug: "right-to-counsel-gap-new-york",
    title: "The Hours Before You Get a Lawyer: New York's Right-to-Counsel Gap",
    category: "Access to Justice",
    date: "2026-07-27",
    excerpt: "New York guarantees a lawyer at arraignment, not before it. What the Hurrell-Harring settlement actually fixed, and what still happens in the hours before that first court appearance."
  },
  {
    slug: "public-defender-caseload-crisis-ny",
    title: "Why Your Public Defender Might Be Carrying 100+ Cases (And What NY Law Says About It)",
    category: "Access to Justice",
    date: "2026-07-27",
    excerpt: "New York's own standards cap public defenders at roughly 300 weighted cases a year, and many offices still can't meet that. Here's what the numbers mean, county by county."
  },
  {
    slug: "what-the-system-doesnt-tell-you",
    title: "The Information Nobody Hands You: Court Dates, Discovery, and Diversion You Have to Ask About Yourself",
    category: "Access to Justice",
    date: "2026-07-27",
    excerpt: "Discovery reform fixed what evidence prosecutors have to turn over. It didn't fix whether anyone explains it to you. Here's exactly what falls through the cracks."
  },
  {
    slug: "language-access-ny-courts",
    title: "When You Don't Understand the Language of Your Own Case: Interpreters, Literacy, and Access in NY Courts",
    category: "Access to Justice",
    date: "2026-07-27",
    excerpt: "About 1.8 million New Yorkers have limited English proficiency and need a court interpreter. The state's interpreter workforce has shrunk by double digits since 2019."
  },
  {
    slug: "nyc-restorative-justice-funding-2026",
    title: "NYC Just Put $6.5 Million Behind Restorative Justice: Here's What That Actually Funds",
    category: "Restorative Justice",
    date: "2026-07-26",
    excerpt: "16 organizations, real circles for real people: students, domestic violence survivors, people in addiction recovery, teens arrested on gun charges. This isn't theory anymore."
  },
  {
    slug: "just-arrested-what-youre-facing",
    title: "You've Just Been Arrested in New York: What You're Actually Facing, and the Question That Changes Everything",
    category: "Restorative Justice",
    date: "2026-07-26",
    excerpt: "What the first hours and days after an arrest actually look like, and the one question about restorative justice that has to be asked before a plea, not after."
  },
  {
    slug: "after-an-arrest-in-new-york",
    title: "What Actually Happens After an Arrest in New York State",
    category: "Rights & Process",
    date: "2026-07-19",
    excerpt: "From the moment of arrest to arraignment, discovery, and sentencing: the full process explained in plain language, so you're not learning these terms for the first time in a courtroom hallway."
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
    excerpt: "Beyond the two-camp framing of 'lock them up' or 'let them off easy': victim-offender dialogue, diversion programs, and community-based alternatives actually running in New York right now."
  }
];
