# Article photos

Drop a photo in here named after the article's slug. That's the whole step —
nothing to edit, nothing to rebuild.

    articles/clean-slate-act-explained.html
    assets/photos/clean-slate-act-explained.jpg   <- name it this

The card picks it up on the next page load. Until a photo exists, that article
keeps showing its generated geometric mark, so the grid is never half-empty
while this folder fills in.

## Format

- **.jpg**, landscape, at least **960 x 540** (cards crop to 16:9, centred).
- Keep files under ~300 KB. They ship in the repo and load on the Articles page.
- For a .png or .webp, or to point two articles at one photo, add an `image`
  line to that article's entry in `assets/data.js` instead:

      {
        slug: "clean-slate-act-explained",
        title: "...",
        image: "assets/photos/clean-slate-hearing.webp",
        imageAlt: "A woman waits on a bench outside a courtroom.",
        imageCredit: "Photo: Dean Mustaphalli",
        ...
      }

## Two things worth getting right

**Alt text.** Add `imageAlt` describing what the photo actually shows. Without
it the photo is treated as decoration — fine, since the headline sits right
next to it, but a real description is better for anyone using a screen reader
and for when the image fails to load.

**Permission and credit.** If someone's face is recognisable, get their okay in
writing before it goes up, and put the source in `imageCredit` — it renders in
the corner of the card. This matters more here than on most sites: a face
attached to a headline about a criminal case is very hard to take back, and it
is the exact harm this site argues against. Photos of places, hands, backs,
crowds and empty rooms carry the story without naming anyone.
