Hi Diana,

Thanks for the patience while you review.

I want to give you a straight answer about exactly what happened, because I think it
will speed up the review and hopefully help you trust that this won't recur.

What I found
------------
On April 22 I deployed a small experimental web app for myself
(forecast.picklewith.me — a tool to preview DUPR rating impacts using the public
forecaster) and configured it with my DUPR account credentials so it could fetch
player profiles when I asked it to.

I did not realize that:

1. The app was running on a public URL that search-engine bots could discover.
2. When a bot crawled my site's player pages, my code had no rate limiting and
   no protection against the kind of auth-retry loop that DUPR's API will trigger.
3. When my JWT expired, every concurrent request my server was handling
   simultaneously tried to re-login, which got 429s, which triggered immediate
   re-retries, which ran in an infinite loop.

I only discovered this when the site stopped responding tonight. I checked the
server logs and found:

  * ~393,000 DUPR API calls in the last 48 hours alone
  * ~787,000 login attempts in the same window
  * Sustained rate of ~11.3 calls/second for roughly 10 consecutive hours
  * The same handful of player-history endpoints called over and over

This is obviously not anything I would do intentionally — it's clearly a buggy
software loop, not a person browsing or scraping data. I have all of the server
logs and am happy to share them with your engineering team so they can confirm
the pattern from your side.

What I have already done
------------------------
1. Killed the runaway server process the moment I noticed.
2. Removed the DUPR credentials from the server entirely (commented them out in
   the .env file and deleted the cached access token), so the app cannot make
   any DUPR calls at all right now even if it wanted to.
3. Added a hard process-wide rate limiter to my code that:
     - caps outgoing DUPR calls at 1 per second, no matter how many concurrent
       requests come in
     - honors the Retry-After header on 429 responses
     - locks the client out for 5 minutes after 3 consecutive 429s, or 2
       consecutive failed logins, so it cannot loop on a flagged account
4. Added robots.txt blocking crawlers from the player pages, so bots stop
     triggering live DUPR calls in the first place.
5. Wrote unit tests for the rate limiter so this can't regress.

I will not re-enable the DUPR credentials on the server until I have verified
all of the above is working in production, and I will not be using my account
for any kind of bulk scraping, ever. The intent of the tool was always to help
me as a coach explain rating math to my students one player at a time — not to
scrape your data.

Why I'm asking for restoration
------------------------------
I am a Level 2 Training Pro at Pickl'r Thornton (PPR + P4 certified) and I'm
in the middle of a DUPR Reset with matches scheduled for this weekend's
tournament. My students rely on my account for their match validations.
Losing access mid-Reset has real downstream consequences for them, not just me.

Coach profile:
https://thornton.thepicklr.com/pros/341849bb-a881-43ef-9555-5a7f616ae73d

I take full responsibility for shipping software that talked to your API
without sufficient safeguards. I'm sorry for the load on your systems. If
there's anything else you need from me — server logs, the diff that added
the rate limiter, a written commitment about acceptable use — I'm happy to
provide it.

Thanks again for the careful review,
Jon Chui
Level 2 Training Pro, PPR and P4 Certified
Coach, Pickl'r Thornton
650-450-7174
