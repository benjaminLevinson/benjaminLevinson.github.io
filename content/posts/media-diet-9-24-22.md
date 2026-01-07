---
title: "Media Diet"
date: 2020-09-15T11:30:03+00:00
# weight: 1
shelves: "media"
author: "Benjamin Levinson"
showToc: true
draft: false
hidemeta: false
comments: true
description: "A short review of the media I’ve consumed this week (week of 9/24/22)"
canonicalURL: "https://blev.dev/posts/media-diet-9-24-22"
disableHLJS: true # to disable highlightjs
disableShare: false
hideSummary: false
searchHidden: false
ShowReadingTime: true
ShowBreadCrumbs: true
ShowPostNavLinks: true
ShowWordCount: true
ShowRssButtonInSectionTermList: true
UseHugoToc: true
cover:
    image: ""
    alt: "" # alt text
    caption: "" # display caption under cover
    relative: false # when using page bundles set this to true
    hidden: false # only hide on current single page
---
## Concerts
### Roxy Music and St. Vincent
![Phil Manzanera shredding](/images/concerts/2022/roxy-music.gif)
Poor Annie Clark- she put on a great show but bad planning at the venue led to most of the theater being half empty with people still streaming into their seats midway through her set. I guess the show sold fewer tickets than they expected because the entire second deck got upgraded to seats on the first deck of the stadium. Logistically, this meant people had to stand in a long line to exchange their bad seats for new seats. Even worse, the audience for Roxy Music was almost entirely upper middle-class, older, white, middle-aged-to-retired couples, which you just wouldn’t expect to be a very good audience for St. Vincent. Annie still did her best to liven things up, even walking off the stage and moving her way through the crowd during one of her songs, going against the flow of people still trying to find their seats while singing her heart out at the same time.

![St. Vincent in the crowd](/images/concerts/2022/st-vincent-crowd.png)

Things were pretty settled by the time Roxy Music came on. Despite that by my estimates, most of the band is in their 70s now, they put on a high-energy show with some killer solos by Phil Manzanera. Bryan Ferry’s clearly lost some of his higher vocal range, but he covered for it pretty well. Going back to the audience for a sec, I’d say most folks were probably more familiar with Avalon-era Roxy Music, which is when they pretty much invented the genre of adult contemporary (albeit with a more artsy vibe and more inherent musical talent than many of their very commercial descendants). Which is why when they played *In Every Dream Home A Heartache*, a song that begins with a several-minute long ode to a sex doll, it was a little funny that all the wine moms and loafer dads were hanging on to every word. The band hit the “punchline” of the song perfectly– Bryan Ferry sang *I blew up your body, but you blew my mind*, the drums kicked in, and Phil Manzanera hit a mind-melting solo. It really was pretty much perfect.

{{< youtube LSniBxXjK_8 >}}

### Dinosaur Jr.
These guys are still in great form. This was one of the loudest shows I’ve been to but I was saved by my trusty earplugs. Their new album **Sweep It Into Space** is pretty good. I’d give *I Ain’t* a listen if you are at all a fan.

{{< youtube QjK8TPjlylw >}}

## Reading
### [*The Productive Programmer*](https://www.amazon.com/Productive-Programmer-Theory-Practice-OReilly/dp/0596519788/), chapter 4, *Canonicality*
In some ways, the fact that this book is so dated is very helpful because the author deals with many problems encountered by the last generation of software engineers. As someone who has been in the industry for less than 5 years, many answers to last generation’s problems have been solved already for me, but the reason we need these solutions in the first place is often glossed over. For example, I had never considered the **canonical build** problem: when a team is working together on a project and one developer's build breaks, how can you tell whether the issue is in the build or in their environment? A team build server solves this issue by providing a team with a **canonical build** on a canonical build server. Because the build server is the source of truth, if a commit breaks the build on the build server, you know there is actually a problem. In other words, a build server provides a way for the team to say, “if the project doesn’t build here, you broke the build with this change”.

One other important takeaway from this week’s chapter: code or schema generation is often a method of keeping your project DRY (as in Don’t Repeat Yourself). The author shows a snippet of code he wrote to generate a data access object (or DAO) Java class to interact with a database that has a particular schema. This generated code helped him have one *canonical* source-of-truth for his data- the database, which they didn’t have control over. He talks about how one could take this in the other direction depending on which aspect of the codebase is the source-of-truth. If the database schema is controlled by you, then your code might be the source of truth and you could generate the schema from your DAO. Personally, I don’t expect to be writing my own database schema generation code anytime soon, but this was great insight into keeping code DRY through canonicality and a helpful reminder that generating code doesn’t have to be that difficult.

## Music
### *Roxy Music* (1972), Roxy Music
This one finally clicked for me, and boy is it great. Don’t miss *Bitter’s End* or *Virginia Plain*. This is a great place to start with Roxy Music if you haven’t heard them yet.

{{< youtube E76oQIHoX4Q >}}

### *Flesh + Blood* (1980), Roxy Music
To be honest, I think I always thought this album would mark when Roxy Music lost their way exploring soulless adult-contemporary, but I found some really enjoyable stuff on here. *Oh Yeah* definitely is a must hear, with a really catchy chorus. Overall, I’d still say the album is inessential but fun if you’re a fan.

{{< youtube zGftnl0KtUY >}}

### *Avalon* (1982), Roxy Music
The album that put adult-contemporary on the map, in my uninformed opinion. Really good! But doesn’t hit quite the same highs of their more proggy classic run of albums for me.

{{< youtube kOnde5c7OG8 >}}

### *Historian* (2018), Lucy Dacus
One of my all-time favorite albums which I’ve listened to tens of times and always get in the mood for on early flights. I related to this one very much senior year of college when I was deconstructing my faith and it’s stuck with me since. It’s hooky, emotionally-resonant art-rock about the passing of the torch from our grandparents’ generation to ours, and one day to our grandchildren.

{{< youtube zGftnl0KtUY >}}

## Movies
### *Three Colors: Red*
Caught this one at Richard Linklater’s Austin Film Society Cinema, which is a must-visit if you live in Austin and like film. I really loved this movie. What appears to be a straightforward plot in the first two acts subtly unfolds in the final act into something unexpected, beautiful, and open-ended. I highly recommend a watch of Red, but be sure to see the also-great Three Colors: Blue and White first so you can catch all of the Three Colors-extended-universe references and cameos. The correct order to see the movies is Blue, White, then Red.

![Three Colors: Red](/images/movies/three-colors-red.jpg)

## Podcasts
* [*Ends of the Earth*](https://www.thisamericanlife.org/779/ends-of-the-earth), **This American Life** - most of this episode is part of an essay by a woman written about her husband who, diagnosed with Alzheimer’s, decides to go through the process of assisted suicide in Switzerland. I think her story may have changed my mind a bit on assisted suicide as a way to pass with dignity, but that didn’t make this any easier of  a listen, although the story was quite poignant at times.
* [*Chapo Control To Major Tom*](https://pod.link/1097417804/episode/13225192301416a2eba93ea10771921e), **Chapo Trap House** - more spoofs and goofs with the boys, fun listen as always.
* *Great War Great Retreat*, episode 59 out of 112, [**Revolutions**](https://podcasts.apple.com/us/podcast/revolutions/id703889772) (season 10, the Bolshevik revolution), Mike Duncan - 59 episodes in, I think I’m finally *into* this podcast. This is a great listen if you’re at all interested in the origins of Soviet socialism, mass movements, or the history of how we got to this moment.

## Hacking
### This blog
I spent much of this week bringing this blog up on Github Pages using Hugo, a static-site generator that allows you to write pages or blog posts in Markdown and easily deploy almost anywhere. There was a small learning curve, but the experience has overall been pretty smooth. Hugo has very easy integration with Disqus for commenting and Google Analytics for keeping tabs on site traffic. Even adding a newsletter was pretty effortless- I followed [a tutorial on Backendology](https://backendology.com/2018/08/31/hugo-newsletter/) where you just create Tiny Letter account, then integrate with a service called Zapier that watches your RSS feed for changes and sends out a newsletter update whenever it detects anything. Very easy. If you’re interested in starting a blog or have a static website you’d like to host, Hugo’s a great tool.
