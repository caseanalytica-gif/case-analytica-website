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
    title: "NYC Landlords Can't Screen You Out for a Criminal Record First Anymore: The Fair Chance for Housing Act Explained",
    category: "Access to Justice",
    format: "Short",
    description: "Since January 2025, most NYC landlords can't ask about or run a criminal background check until after a conditional offer, and can only count convictions inside a specific lookback window.",
    youtubeId: "",
    published: false
  },
  {
    title: "New York Suspended Its Own Solitary Confinement Law. Here's What the HALT Act Still Says",
    category: "System",
    format: "Short",
    description: "New York's HALT Act caps solitary confinement at 15 consecutive days. In February 2025 the state suspended that cap in its own prisons, and a court fight over the suspension is still open.",
    youtubeId: "",
    videoFile: "assets/video/halt-act-solitary-confinement-suspended-ny.mp4",
    poster: "assets/video/halt-act-solitary-confinement-suspended-ny-poster.jpg",
    published: true
  },
  {
    title: "What Is Your Right to a Speedy Trial in New York? CPL 30.20 and the Test Courts Actually Use",
    category: "Rights & Process",
    format: "Short",
    description: "New York guarantees a speedy trial under CPL 30.20, but there's no fixed number of days attached to it, unlike the separate statutory CPL 30.30 clock. Here's the five-factor test courts actually use.",
    youtubeId: "",
    published: false
  },
  {
    title: "What Happens If You Violate Probation in New York? CPL 410.70 Explained",
    category: "Rights & Process",
    format: "Short",
    description: "New York's probation violation hearing runs on a lower burden of proof than the case that put you on probation, with no jury and a judge deciding alone.",
    youtubeId: "",
    published: false
  },
  {
    title: "Can You Plead Guilty in New York Without Admitting You Did It? The Alford Plea Explained",
    category: "Restorative Justice",
    format: "Short",
    description: "New York allows a guilty plea without an admission of guilt, called an Alford plea, but courts have ruled it can still be held against you years later at parole.",
    youtubeId: "",
    published: false
  },
  {
    title: "New York Can Only Hold You 120 Hours on a Felony Complaint: CPL 180.80 Explained",
    category: "Rights & Process",
    format: "Short",
    description: "CPL 180.80 requires New York to release someone held on a felony complaint after 120 or 144 hours with no indictment or hearing, but only if someone actually files for it.",
    youtubeId: "",
    published: false
  },
  {
    title: "Police Can Take Your Cash Without Charging You: Civil Asset Forfeiture in New York Explained",
    category: "Rights & Process",
    format: "Short",
    description: "New York can seize cash, cars, and homes through a civil lawsuit that runs separately from any criminal case, and doesn't require a conviction to keep the property.",
    youtubeId: "",
    published: false
  },
  {
    title: "Your Old Marijuana Conviction May Already Be Expunged in New York (MRTA Explained)",
    category: "System",
    format: "Short",
    description: "New York automatically expunged a specific list of marijuana convictions starting in 2021, with no filing, no fee, and no notice sent to the people it affects.",
    youtubeId: "",
    published: false
  },
  {
    title: "What Happens If You Miss a Court Date in New York? The 30-Day Rule Nobody Explains",
    category: "System",
    format: "Short",
    description: "A missed court date and an active bench warrant are not the same emergency. New York's bail jumping law only becomes a separate charge if you don't turn yourself in within a specific statutory window.",
    youtubeId: "",
    published: false
  },
  {
    title: "Can NYPD Stop and Frisk You Without a Reason? CPL 140.50 and Floyd v. City of New York Explained",
    category: "Rights & Process",
    format: "Short",
    description: "Reasonable suspicion is a specific legal standard, not a phrase that excuses any stop. Here's what CPL 140.50 authorizes and what a 2013 federal ruling found NYPD was doing instead.",
    youtubeId: "",
    published: false
  },
  {
    title: "The Bet Every Plea Deal Is Making",
    category: "Restorative Justice",
    format: "Short",
    description: "A plea offer is priced on a guess about what you won't do. Here's the bet baked into every deal, and the question that tells you if it's a safe one.",
    youtubeId: "",
    published: false
  },
  {
    title: "Project Reset in New York: How a Desk Appearance Ticket Can Avoid a Criminal Record",
    category: "Restorative Justice",
    format: "Short",
    description: "Project Reset lets people arrested in NYC for a low-level misdemeanor avoid prosecution entirely by completing a short community program, but only if they find out about it before their court date.",
    youtubeId: "",
    published: false
  },
  {
    title: "How Long Can New York Take You to Trial? CPL 30.30 Speedy Trial Rules Explained",
    category: "Rights & Process",
    format: "Short",
    description: "CPL 30.30 doesn't guarantee a trial by a deadline, it sets a clock for when prosecutors have to say they're ready, and that clock has more exceptions than most people realize.",
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
    slug: "queens-chain-snatching-arrest-process-ny",
    title: "What Happens After an Arrest in NYC: A Queens Chain-Snatching Case Shows the Timeline From Custody to Arraignment",
    category: "Rights & Process",
    date: "2026-08-21",
    excerpt: "A Queens chain-snatching case involving a 16-year-old shows how booking, arraignment, bail, and diversion actually work after an NYC arrest, and where Raise the Age changes the sequence."
  },
  {
    slug: "protect-our-courts-act-ny-explained",
    title: "The Protect Our Courts Act: Why ICE Needs a Judicial Warrant to Arrest You at a NY Courthouse",
    category: "Rights & Process",
    date: "2026-08-19",
    excerpt: "New York's Protect Our Courts Act bars civil arrests at state courthouses unless a judge, not an ICE supervisor, signed the warrant. A federal judge upheld the law in November 2025. Here's what it actually covers."
  },
  {
    slug: "medical-parole-terminally-ill-ny",
    title: "Medical Parole in New York: How a Terminally Ill or Debilitated Person Can Actually Get Out",
    category: "Rights & Process",
    date: "2026-08-19",
    excerpt: "New York lets DOCCS and the Parole Board release a terminally ill or severely debilitated incarcerated person under Executive Law 259-r and 259-s. A family member can request it directly, but most requests never make it to a hearing."
  },
  {
    slug: "extreme-risk-protection-order-ny-explained",
    title: "New York Can Take Your Guns Without a Criminal Charge: The Red Flag Law Explained",
    category: "Rights & Process",
    date: "2026-08-15",
    excerpt: "New York's red flag law lets a court order guns removed through a civil case, not a criminal one, often before the person involved has spoken to a lawyer. Here's what CPLR Article 63-A actually allows."
  },
  {
    slug: "motion-to-suppress-evidence-ny-explained",
    title: "Can Evidence Get Thrown Out Before Trial? What a Suppression Hearing in New York Actually Does",
    category: "Rights & Process",
    date: "2026-08-15",
    excerpt: "A Mapp, Huntley, or Dunaway motion can get illegally obtained evidence thrown out before a plea is ever discussed. Here's what CPL 710.20 actually lets a defendant challenge."
  },
  {
    slug: "violation-of-parole-executive-law-259-i-ny",
    title: "What Happens If You Violate Parole in New York? Executive Law \u00a7 259-i Explained",
    category: "Rights & Process",
    date: "2026-08-14",
    excerpt: "Parole violation runs on a different law than probation violation, with its own hearings, deadlines, and burden of proof. Here's what Executive Law 259-i actually requires before parole can be revoked."
  },
  {
    slug: "cpl-160-50-sealing-favorable-termination-ny",
    title: "Your Case Was Dismissed. Was Your Arrest Record Sealed? CPL 160.50 Explained",
    category: "Access to Justice",
    date: "2026-08-14",
    excerpt: "New York automatically seals your arrest record after a dismissal, acquittal, or other favorable result under CPL 160.50, no petition required. Here's what actually gets sealed, and who can still see it."
  },
  {
    slug: "correction-law-article-23-a-employment-ny",
    title: "Can a New York Employer Reject You Because of a Conviction? What Correction Law Article 23-A Actually Requires",
    category: "Access to Justice",
    date: "2026-08-13",
    excerpt: "A conviction on a background check is not, by itself, a legal reason to turn someone away from a job in New York. Correction Law Article 23-A requires an individualized analysis first. Here's what the law actually requires, and the factors that decide it."
  },
  {
    slug: "cpl-730-competency-to-stand-trial-ny",
    title: "Found Unfit to Stand Trial in New York? What CPL Article 730 Actually Allows",
    category: "Rights & Process",
    date: "2026-08-13",
    excerpt: "A finding of unfit to proceed under CPL Article 730 doesn't end a case, it pauses it. New York can hold someone in psychiatric custody for up to two-thirds of the maximum sentence the top charge carries. Here's how the process actually works."
  },
  {
    slug: "cpl-440-10-motion-to-vacate-conviction-ny",
    title: "Is the Case Really Over Once You're Convicted? What CPL 440.10 Actually Lets You Do in New York",
    category: "Access to Justice",
    date: "2026-08-03",
    excerpt: "A conviction isn't always the end of the road. CPL 440.10 lets a New York court vacate a judgment for reasons that never made it onto the record, but it comes with procedural traps that can shut the door for good if you miss them."
  },
  {
    slug: "grand-jury-testify-cpl-190-50-ny",
    title: "Can You Testify Before Your Own Grand Jury in New York? What CPL 190.50 Actually Requires",
    category: "Rights & Process",
    date: "2026-08-02",
    excerpt: "New York gives you the right to testify before the grand jury deciding your own case, but only if you ask in writing before an indictment is filed. Here's how CPL 190.50 actually works, and the deadline that erases the right if you miss it."
  },
  {
    slug: "right-to-testify-grand-jury-cpl-190-50-ny",
    title: "Do You Have the Right to Testify Before the Grand Jury in New York? CPL 190.50 Explained",
    category: "Rights & Process",
    date: "2026-08-02",
    excerpt: "There is no constitutional right to testify before a New York grand jury. There is a statutory one, under CPL 190.50, and it disappears fast if nobody files the notice in time."
  },
  {
    slug: "domestic-violence-survivors-justice-act-ny",
    title: "What Is the Domestic Violence Survivors Justice Act in New York? Penal Law 60.12 Explained",
    category: "Restorative Justice",
    date: "2026-08-02",
    excerpt: "Penal Law 60.12 lets a judge hand down a lighter sentence when abuse was a significant reason someone ended up charged. In April 2026, New York's highest court ruled a prosecutor can't make you sign away the hearing that proves it."
  },
  {
    slug: "dvsja-penal-law-60-12-domestic-violence-survivors-ny",
    title: "The Domestic Violence Survivors Justice Act in New York: What Penal Law 60.12 Actually Does",
    category: "Restorative Justice",
    date: "2026-08-02",
    excerpt: "Penal Law 60.12 lets a judge hand down a shorter sentence to a domestic violence survivor whose abuse drove the offense. A prosecutor cannot make you waive that hearing to get a plea deal, the Court of Appeals said so in April 2026."
  },
  {
    slug: "bronx-criminal-court-logistics",
    title: "Bronx Criminal Court: Which Building, Which Train, What to Expect",
    category: "Rights & Process",
    date: "2026-08-20",
    excerpt: "\"Bronx Criminal Court\" is two different buildings a block and a half apart, 215 and 265 East 161st Street, and both go by that name. How to find out which one you need before you travel, plus arraignment hours that run to 1:00 a.m. seven days a week."
  },
  {
    slug: "queens-criminal-court-logistics",
    title: "Queens Criminal Court: Getting There, Getting In, and the 11 p.m. Cutoff",
    category: "Rights & Process",
    date: "2026-08-20",
    excerpt: "Queens arraignments stop at 11:00 p.m., not 1:00 a.m. like the Bronx, and people assume every borough runs the same hours. Where the Kew Gardens courthouse is, how to get in, and which clerk windows close early."
  },
  {
    slug: "closing-rikers-root-cause-prevention-ny",
    title: "Root-Cause Prevention Is the Part of Closing Rikers Nobody Budgets For",
    category: "System",
    date: "2026-08-20",
    excerpt: "Advocates say closing Rikers means treating housing and mental health needs instead of jailing them. The city already spends $507,000 a year per person there, and 87 percent of them haven't been convicted. Here's what the prevention argument rests on, and where the evidence is thinner than the slogan."
  },
  {
    slug: "fair-chance-for-housing-act-nyc-explained",
    title: "New York City Landlords Can't Screen You Out for a Criminal Record First Anymore: The Fair Chance for Housing Act Explained",
    category: "Access to Justice",
    date: "2026-08-14",
    excerpt: "Since January 2025, most NYC landlords can't ask about or run a criminal background check until after a conditional offer, and can only count convictions inside a specific lookback window. Here's what the Fair Chance for Housing Act actually restricts."
  },
  {
    slug: "halt-act-solitary-confinement-suspended-ny",
    title: "New York Suspended Its Own Solitary Confinement Law. Here's What the HALT Act Still Says",
    category: "System",
    date: "2026-08-14",
    excerpt: "New York capped solitary confinement at 15 consecutive days under the HALT Act. In February 2025, the state suspended it anyway, and a court fight over that suspension, Smalls v. Martuscello, is still open."
  },
  {
    slug: "why-rikers-island-should-close-ny",
    title: "Why Rikers Island Should Close, and What Could Actually Replace It",
    category: "System",
    date: "2026-08-13",
    excerpt: "Rikers costs roughly $1,389 a day per person, the borough jails meant to replace it are up to five years behind schedule, and they still won't have enough beds. Here's the closure case, and what already keeps people showing up to court for a fraction of the cost."
  },
  {
    slug: "rikers-detention-plea-leverage-ny",
    title: "How Holding Someone at Rikers Becomes Leverage for a Plea",
    category: "Restorative Justice",
    date: "2026-08-13",
    excerpt: "Research reviewed by the Vera Institute found pretrial detention makes people up to 46 percent more likely to plead guilty. Here's how a bed at Rikers turns into bargaining leverage, and what happens to that leverage if the jail population shrinks."
  },
  {
    slug: "right-to-speedy-trial-cpl-30-20-ny",
    title: "What Is Your Right to a Speedy Trial in New York? CPL 30.20 and the Test Courts Actually Use",
    category: "Rights & Process",
    date: "2026-08-08",
    excerpt: "New York guarantees a speedy trial under CPL 30.20 and Civil Rights Law 12, but there's no fixed number of days attached to it. Here's the five-factor balancing test courts actually apply, and how it's different from the CPL 30.30 deadline."
  },
  {
    slug: "violation-of-probation-cpl-410-70-ny",
    title: "What Happens If You Violate Probation in New York? CPL 410.70 Explained",
    category: "Rights & Process",
    date: "2026-08-08",
    excerpt: "Probation ends the case, until it doesn't. CPL 410.70 lets a judge revoke probation and impose the original sentence on a lower burden of proof, with no jury. Here's how the hearing actually works."
  },
  {
    slug: "rikers-island-cost-per-person-ny",
    title: "What Rikers Island Actually Costs, Per Person, Per Year",
    category: "System",
    date: "2026-08-07",
    excerpt: "New York City spent $507,000 per incarcerated person in 2023, and most of the people held at Rikers Island haven't been convicted of anything. Here's what the city's own numbers show."
  },
  {
    slug: "alford-plea-new-york-explained",
    title: "Can You Plead Guilty in New York Without Admitting You Did It? The Alford Plea Explained",
    category: "Restorative Justice",
    date: "2026-08-07",
    excerpt: "New York allows a guilty plea without an admission of guilt, called an Alford plea. New York's own courts have ruled it can still be held against you years later, at a parole hearing."
  },
  {
    slug: "cpl-180-80-release-from-custody-ny",
    title: "How Long Can New York Hold You on a Felony Complaint? CPL 180.80's 120-Hour Rule",
    category: "Rights & Process",
    date: "2026-08-07",
    excerpt: "CPL 180.80 says New York must release you on your own recognizance after 120 or 144 hours on a felony complaint with no indictment or hearing. It only works if someone actually applies for it."
  },
  {
    slug: "parole-hearing-preparation-ny",
    title: "A Parole Hearing in New York Can Last Twenty Minutes: How to Actually Prepare for One",
    category: "Rights & Process",
    date: "2026-08-06",
    excerpt: "A NY parole hearing usually runs ten to twenty minutes. Here's what the Board actually evaluates, how to build a release plan that holds up, and what to say and never say in the room."
  },
  {
    slug: "civil-asset-forfeiture-cplr-13a-ny",
    title: "Police Can Take Your Cash Before You're Ever Charged: Civil Asset Forfeiture Under CPLR Article 13-A",
    category: "Rights & Process",
    date: "2026-08-06",
    excerpt: "New York can seize your cash, your car, or your house without a conviction, sometimes without an arrest. Here's what CPLR Article 13-A actually allows, and the exact question to ask if it happens to you."
  },
  {
    slug: "mrta-marijuana-expungement-ny",
    title: "Your Old Marijuana Conviction May Already Be Expunged in New York: What the MRTA Actually Cleared",
    category: "Access to Justice",
    date: "2026-08-06",
    excerpt: "New York automatically expunged hundreds of thousands of marijuana convictions under the MRTA, no filing and no fee required. Here's exactly which charges qualify, and what to do if yours doesn't."
  },
  {
    slug: "missed-court-date-bench-warrant-ny",
    title: "What Happens If You Miss a Court Date in New York? Bench Warrants and the 30-Day Window",
    category: "System",
    date: "2026-08-03",
    excerpt: "A missed court date and an active bench warrant are not the same emergency. Here's what CPL 530.70 actually authorizes, and the statutory 30-day window that decides whether you're also charged with bail jumping."
  },
  {
    slug: "stop-and-frisk-cpl-140-50-ny",
    title: "Can NYPD Stop and Frisk You Without a Reason? CPL 140.50 and Floyd v. City of New York",
    category: "Rights & Process",
    date: "2026-08-03",
    excerpt: "Reasonable suspicion is a legal standard with an actual definition, not a phrase that excuses any stop. Here's what CPL 140.50 authorizes, what Floyd v. City of New York found NYPD was doing instead, and what to say during a stop."
  },
  {
    slug: "why-innocent-people-plead-guilty-ny",
    title: "Why Do Innocent People Plead Guilty? The Trial Penalty Behind New York's Guilty-Plea Rate",
    category: "Restorative Justice",
    date: "2026-08-02",
    excerpt: "Nationally, 97 percent of felony convictions in large urban courts come from a guilty plea, not a trial. Here's the pressure that pushes innocent people into that number, and what New York law does and doesn't do about it."
  },
  {
    slug: "discovery-platform-access-logs-work-product-ny",
    title: "Is the DA Watching When You Open Your Case File? Discovery Platforms and Work Product in NY",
    category: "Rights & Process",
    date: "2026-08-02",
    excerpt: "Digital evidence platforms log every time a defense file gets opened. That access log can say more about defense strategy than the DA is supposed to see, and New York's work-product rule under CPL 245.65 was written before anyone thought to ask about it."
  },
  {
    slug: "bail-source-hearing-ny-explained",
    title: "Your Bail Is $100. Why Are You Still in Jail? What a Bail Source Hearing Actually Does",
    category: "Rights & Process",
    date: "2026-08-01",
    excerpt: "A low bail number isn't the same as being free to go. Here's how a bail source hearing under CPL 520.10 can keep someone in jail for a week or two on bail that was never the real barrier, and the exact question to ask about it."
  },
  {
    slug: "cpl-160-59-sealing-vs-expungement-ny",
    title: "Can You Actually Expunge a Criminal Record in New York? What CPL 160.59 Sealing Really Does",
    category: "Access to Justice",
    date: "2026-08-01",
    excerpt: "New York doesn't expunge convictions, no matter what that search brings up. Under CPL 160.59, a conviction can be sealed after ten years, but only if you ask, only if it qualifies, and only if the paperwork is filed correctly. Here's what the motion actually requires."
  },
  {
    slug: "project-reset-desk-appearance-ticket-ny",
    title: "What Is Project Reset in New York? How a Desk Appearance Ticket Can Avoid a Criminal Record",
    category: "Restorative Justice",
    date: "2026-08-01",
    excerpt: "Project Reset lets people arrested in New York City for a low-level misdemeanor avoid prosecution entirely, but only if the person holding the Desk Appearance Ticket finds out about it before the court date. Here's how it actually works, and the exact question to ask."
  },
  {
    slug: "cpl-30-30-speedy-trial-ny-explained",
    title: "How Long Can New York Take You to Trial? CPL 30.30 Speedy Trial Rules Explained",
    category: "Rights & Process",
    date: "2026-08-01",
    excerpt: "CPL 30.30 doesn't promise a trial by a deadline. It sets a clock for when prosecutors have to say they're ready. Here's what the clock actually measures, what stops it, and the question to ask your attorney about it."
  },
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
