# Building a Custom App With an LLM: The Climbing Weather Checker

This lesson walks through how a non-programmer can use an LLM coding assistant to build a real little app, one feature
at a time.

The example app answers a very normal outdoor-person question:

> I want to go climbing. Which crag has the best weather?

That is the whole magic trick. Start with a real-life annoyance, describe it clearly, then keep asking for one useful
improvement at a time. Tiny steps. Big vibes.

## Before You Start

You do not need to be a "real programmer" to do this. You do need three things:

- A clear idea of what you want the app to do.
- A willingness to test it and say what feels wrong.
- Enough patience to build it in layers instead of trying to make the perfect app in one giant leap.

The user's job is not to know all the code. The user's job is to know what they want the app to do.

The LLM's job is to translate your ideas into code, explain tradeoffs, and keep the project from turning into spaghetti.

## Tiny Vocabulary Pit Stop

Here are a few words programmers use constantly. None of them are sacred. They are just labels for normal ideas.

- **LLM**: a Large Language Model, like ChatGPT or a coding assistant. It is the thing you talk to in plain English.
- **App**: a tool that does a job. It can be a website, phone app, command-line script, spreadsheet automation, or tiny
  robot helper.
- **CLI**: Command-Line Interface. This means you run the app by typing a command into a terminal, instead of clicking
  buttons on a website. It is often the fastest way to make the first working version.
- **Terminal**: the text window where commands run. It looks old-school, but it is very useful.
- **Script**: a small program, often one file, that does a task.
- **API**: Application Programming Interface. Translation: a way for one program to ask another program for information
  or action.
- **Endpoint**: one specific API web address. If an API is a restaurant, an endpoint is one item on the menu.
- **Cache**: saved data. If the app already asked for Tuesday's weather, it can reuse that answer instead of asking
  again immediately.
- **HTML**: the basic file format for web pages.
- **JSON**: a common data format apps use to pass information around. It looks like organized lists and labels.
- **Python**: the programming language used for this app's script.
- **JavaScript**: the programming language that runs inside a web page after it opens in your browser.
- **Static website**: a website made of files that can be hosted cheaply because it does not need a server doing custom
  work for every visitor.
- **Backend**: code that runs somewhere other than the user's browser, usually on a server. This app mostly avoids
  needing one.
- **Database**: a structured place to store information. This app does not need one yet.
- **Latitude and longitude**: map coordinates. Weather tools often use these instead of place names.
- **Git**: a save-history system for code.
- **Commit**: a named checkpoint in Git. Like "save game," but for your project.
- **GitHub Actions**: a way to tell GitHub, "run this task for me on a schedule or when I update the project."
- **GitHub Pages**: a way to host a simple website from a GitHub project.
- **Cron**: a compact schedule format computers use. For example, "run this every Monday morning."

If those still sound fuzzy, that is fine. You only need enough understanding to ask the next good question.

## The Basic Loop

Almost every feature followed this loop:

1. Say the next thing you want.
2. Let the LLM inspect the existing project.
3. Let it make the change.
4. Run the app or tests.
5. Notice what is missing or weird.
6. Ask for the next improvement.

That is app development. It is not glamorous. It is just a bunch of small "wait, actually..." moments stacked into
something useful.

## Chapter 1: Start With the Smallest Useful App

Changelog feature:

- Add prototype CLI for ranking local climbing areas by forecast climbability.

The first version did not need accounts, maps, animations, push notifications, or a majestic startup logo. It just
needed to answer:

> Given a date, rank my climbing areas by whether the weather looks climbable.

A good beginner prompt:

```text
Make a prototype CLI script. I want to pass a date and get a sorted list of local climbing areas with a climbability percentage.
Use these areas: Donner Summit, Sugar Loaf, Lovers Leap, South Lake Tahoe, The Emeralds, The Grotto, Yosemite, Castle Rock, Auburn Quarry.
```

Why this works:

- "CLI script" keeps the first version simple.
- The input is obvious: a date.
- The output is obvious: a ranked list.
- The data is concrete: named climbing areas.

Beginner lesson: Do not start by asking for "an app." Ask for one useful behavior.

## Chapter 2: Create a Simple Scoring Rule

Changelog features:

- Add weather forecast integration.
- Add local climbing areas.
- Add basic climbability scoring.

Start with a very plain rule:

```text
No rain and temp <= 75 means 100% climbable.
```

That rule is not meteorology. It is a starting point. Starting points are allowed to be goofy. You can improve them once
the app exists.

The next step is to add weather data from a weather data service and calculate a score using:

- high temperature
- precipitation amount
- precipitation probability
- wind

A non-technical prompt should sound like this:

```text
I need a website or something that can tell me the real weather forecast for each climbing area.
I don't know what weather source to use.
Please find a simple free option, explain it in plain English, and wire it into the app.
```

That prompt works because it does not pretend you know the technical answer. You are telling the LLM the result you
need: real weather for real places.

For this example app, a free no-key weather service is a good fit. "No-key" means there is no account setup and no
secret
password to paste into the app. Nice and low drama.

When choosing a weather source, ask the LLM to explain:

- Is it free?
- Does it need an account or API key?
- Can it forecast by latitude and longitude?
- Does it provide the details we need, like rain chance, temperature, and wind?
- Is it allowed to be used in a small personal project?

## Chapter 3: Make the Output Useful in Real Life

Changelog features:

- Add `--by-distance` sorting.
- Add `Miles/Time` output using `miles / 35`, rounded to half-hour increments.

Weather is not the only question. Sometimes the best crag is three hours away and you only have half a day.

Next, add distance and rough travel time:

```text
If I pass a --by-distance flag, then distance is the main sort key.
Change Miles to Miles/Time, like 112/~3h, using time = miles / 35 and rounding to .5 hours.
```

This is a very good LLM request because it includes examples. Examples are gold. Tiny little treasure nuggets.

Beginner lesson: When you know what the output should look like, show an example.

## Chapter 4: Add Cache So You Do Not Annoy the Weather Service

Changelog feature:

- Add local response caching and `--refresh`.

An API is just a service your app talks to over the internet. For this app, the question is basically:

> Hey weather service, what is the forecast for this latitude and longitude?

The exact web address the app calls is called an endpoint. The important idea is simple: the app asks a weather service
for structured weather data.

You generally do not want to call the weather service over and over if the answer has not changed.

Add a cache with a prompt like this:

```text
Add a local cache so we don't spam the weather service, with --refresh to refresh the cache.
```

That gives the app two modes:

- Normal run: use cached weather if it already exists.
- Refresh run: ask the weather service again.

Beginner lesson: Once your app talks to another website or service, ask about caching, errors, and what happens when the
internet is sad.

## Chapter 5: Keep a Changelog

Changelog feature:

- Track features as they are added.

A changelog is a simple project diary. It lists what changed, usually grouped by date or release.

That is a nice habit: keep a simple file that says what was added, fixed, changed, and planned.

Good prompt:

```text
Create a CHANGELOG.md file and keep it updated as features are added.
Use it as a chapter list for what the app can do.
```

Why this matters:

- You remember what was built.
- New readers can understand the project history.
- The LLM has a better map when you come back later.

Beginner lesson: Documentation is not homework. It is a memory upgrade for your project.

## Chapter 6: Make a Pretty HTML Report

Changelog features:

- Add `--html` CLI output.
- Use a climbing-themed background image.
- Embed report data in HTML.

The CLI is useful, but not exactly "send this to someone" friendly.

Ask for a shareable report:

```text
Next feature: make a pretty HTML output report, still from CLI but with --html.
Use a nice climbing themed background, ideally with local crag vibes.
```

The key move: the command-line script still does the work, but it can now produce a nice static HTML file.

That means the app is still simple. No database. No login. No server running all day. Just generate a page and open it.

Beginner lesson: A "real app" does not always need a database. Plain HTML can be plenty powerful.

## Chapter 7: Add Interactivity Without Making Things Complicated

Changelog features:

- Support in-page origin changes from Folsom, Auburn, and Cameron Park.
- Add in-page distance sorting.

The next request made the HTML page interactive:

```text
For the HTML, embed the data in it. Add a dropdown for distance from Folsom, Auburn, and Cameron Park. Let the page sort by distance.
```

This is a great pattern:

- Python gathers weather.
- Python writes all the data into the HTML file.
- JavaScript inside the page recalculates distance and sorting.

Translation:

- Python does the behind-the-scenes work.
- HTML is the page you look at.
- JavaScript makes the page respond when you click dropdowns and checkboxes.

No server needed. Still cheap. Still portable.

Beginner lesson: Ask the LLM to keep the architecture simple. "Can this be done in the static page?" is a very useful
question.

## Chapter 8: Turn One Day Into a Week

Changelog features:

- Add 7-day HTML forecast reports with day tabs.
- Add a week overview grid with top 5 places by date and hover details.

Once the one-day report works, make it more useful:

```text
Next, add a weekly forecast for the next 7 days, with tabs for each day.
The landing page should show a grid with the top 5 places to climb for the next 7 days.
Dates as columns, places as rows, cells color-coded with percent as value, hover for details.
```

This is a bigger feature, but notice how specific it is:

- 7 days
- tabs
- overview grid
- top 5 places
- color-coded cells
- hover details

The more concrete you are, the less the LLM has to guess.

Beginner lesson: Big features become manageable when you describe the screen in plain language.

## Chapter 9: Publish It for Cheap

Changelog features:

- Add GitHub Pages publishing through GitHub Actions.
- Add resilient Pages builds that fall back to cached weather data if refresh fails.
- Run the workflow weekly on Mondays.

For hosting, ask:

```text
What would be the cheapest way to run and host this?
```

For this style of app, yes. More generally, the cheapest path is usually:

- use a scheduled automation to generate a report
- publish that report as a static website
- avoid running a paid server all day

In the example app, GitHub Actions is the scheduled automation and GitHub Pages is the static website host.

How it works:

- GitHub Actions runs the script.
- The script generates `index.html`.
- GitHub Pages hosts that file.
- A schedule runs it automatically.

The schedule can be changed to Mondays:

```yaml
schedule:
  - cron: "0 13 * * 1"
```

That little `cron` line is the schedule. It means every Monday at 13:00 UTC. UTC is a standard global time zone
computers use, so you often have to translate it to your local time.

Beginner lesson: Hosting can be simple if your app can generate a static report. You can ask the LLM, "What is the
cheapest way to run this once a week and publish the result?"

## Chapter 10: Add Links That Help Humans

Changelog features:

- Link crag names to Mountain Project.
- Link weather values to a second weather source for verification.

A report should not just give answers. It should help people verify them.

Add helpful links with a prompt like this:

```text
Link each crag label to the Mountain Project area.
Make the weather text link to a second source for verification.
```

Now:

- Crag names open Mountain Project.
- Weather numbers open another forecast website, so a human can sanity-check the app.

This is a subtle but excellent product move. It builds trust without pretending the app is perfect.

Beginner lesson: When data might be wrong, add source links instead of hiding the uncertainty.

## Chapter 11: Add Real-World Domain Rules

Changelog features:

- Add sandstone wet-weather protection.
- Mark Castle Rock State Park as sandstone.

Then came a climbing-specific rule:

```text
If a crag is sandstone, you aren't supposed to climb on it for 2 days after last rain.
The only one in the starter list is Castle Rock.
Add a rule that will check for wet weather on prior days for sandstone crags.
Those rows become 0% for the two days after last rain.
```

This is where custom apps shine. A generic weather app does not know climbing ethics. Your app can.

The implementation adds:

- rock type metadata
- a sandstone checker
- a 2-day rain lookback
- score override to `0%`

Beginner lesson: The best custom apps encode your weird little expert rules. That is the secret sauce.

## Chapter 12: Add Filters and More Area Types

Changelog features:

- Add climbing type metadata for sport, trad, top-rope, and bouldering.
- Add `--types` filtering.
- Add Sacramento-area bouldering locations.
- Add in-page HTML type filters.

Next, add bouldering areas and climbing-type filters:

```text
Add a way to distinguish different types of climbing at a crag, bouldering; top-rope, sport, and trad.
Use it to filter locations.
By default, Boulder types are unselected.
```

The first version might add CLI filtering only. A user-facing check can catch that:

```text
I just ran a report and I don't see the filters?
```

That was a great bug report. It told the LLM what was wrong from the user's point of view.

Then fix the HTML page too:

- Add checkboxes for sport/trad/top-rope/boulder.
- Leave boulder unchecked by default.
- Embed all data in the page so bouldering can be toggled on.

Beginner lesson: "I don't see it" is useful feedback. You do not need to diagnose the bug. Just describe what happened.

## Chapter 13: Test Before You Trust

Throughout development, ask the LLM to run tests like:

```bash
python3 -m unittest -v
python3 -m py_compile climb_weather.py
```

You do not need to understand every test. Think of tests as little robot assistants that check whether old features
still work after new changes.

A good prompt:

```text
Add tests for this behavior.
```

Or:

```text
Before you commit, run the tests.
```

Beginner lesson: Tests are seatbelts. Slightly boring. Very worth it.

## Chapter 14: Commit in Safe Chunks

After each meaningful feature, ask for a commit:

```text
commit
```

A commit is a saved checkpoint in Git. It means:

- This version worked.
- It is easy to see what changed.
- It is possible to go back if needed.

Good commit-sized chunks from this example:

- initial CLI prototype
- HTML report
- 7-day forecast
- GitHub Pages publishing
- forecast verification and sandstone rules
- climbing type filters and weekly schedule

Beginner lesson: Commit after meaningful progress, especially after tests pass.

## Prompting Tips for Non-Technical Builders

Use plain English. Seriously. This is fine:

```text
The page is useful, but I want the weather numbers to link to another forecast so readers can double-check it.
```

Be specific about examples:

```text
Show Miles/Time like 112/~3h.
```

Tell the LLM what matters:

```text
Do good coding practices.
Keep magic numbers in constants.
Don't spam the weather service.
```

Report what you see:

```text
I ran the report and I don't see the filters.
```

Ask for verification:

```text
Run the tests and generate a sample report.
```

## A Simple Recipe to Reuse

Here is the reusable recipe:

1. Pick a real annoyance.
2. Make the smallest command-line version.
3. Add real data.
4. Add caching.
5. Add a prettier output.
6. Add interactivity.
7. Publish it cheaply.
8. Add expert rules.
9. Add filters.
10. Test and commit.

That is it. That is the whole little parade.

The real skill is not "knowing how to code already." The skill is learning how to describe what you want, try the
result, and keep steering.

## Final Pep Talk

LLMs are not magic app fairies. They are more like very fast coding partners who need clear direction and occasional
adult supervision.

You bring the idea, the taste, the domain knowledge, and the "hmm, that feels wrong." The LLM brings code, structure,
tests, and lots of patience.

Together, you can absolutely build useful little apps.

Start tiny. Be specific. Test often. Save your progress.

And when in doubt, say:

```text
Make the simplest working version first.
```

That sentence is basically a cheat code.
