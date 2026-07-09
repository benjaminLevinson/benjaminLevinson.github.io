---
title: What if you gave everyone an intern?
date: 2026-07-09
draft: false
author: Benjamin Levinson
cover:
  relative: false
  hidden: false
post_meta:
  showToc: false
  TocOpen: false
  hidemeta: false
  comments: true
  disableShare: false
  hideSummary: false
  searchHidden: false
  ShowReadingTime: true
  ShowBreadCrumbs: true
  ShowPostNavLinks: true
  ShowWordCount: true
---
If you gave everyone an intern, would your team be more efficient? For anyone who has either been an intern or had an intern, I think the answer is emphatically and obviously **no**. There are many reasons to hire an intern, but speaking from my experience as a one-time intern and now years later as a senior FAANG engineer, you don't hire an intern to make the software development lifecycle more efficient.

Although there are surely many differences between human interns and AI coding agents, I think that the impact on the software development lifecycle of handing off a project to an intern versus handing off a project to a coding agent is similar enough to make this a useful lens for understanding why, even with such capable models (or capable interns!), many companies are failing to see measurable productivity gains from letting their software engineers loose on AI models.

As a reminder, here's how having an intern works:

- You give them a mentor and a hopefully well-reasoned project spec and you let them work independently to deliver that project.
- An intern might build a whole polished-looking feature or app and demo it at the end of their internship. Hopefully, everyone will be impressed!

But would you actually launch that project to production? Even if the mentor has been reviewing the code, you probably won't- because there's a big difference between reading code and understanding how it all fits together. For any company with a reputation to protect and an engineering bar to uphold (which of course isn't every company), they wouldn't just let customers use the intern's project out the gate.

## The Understanding Tax

Here is where the promise of an intern making your team more efficient starts to fade. Most companies won't launch a new product or significant feature without a thorough review- security, maintainability, auditability, performance, and fault-tolerance all play in here. Can you imagine going through an enterprise launch review for a product or feature without a thorough understanding of how it even works?

In my experience, this understanding burden is great enough that most intern projects get thrown away after the intern is gone. After all, the only person who knew how to maintain the project isn't at the company anymore.

All of these tradeoffs are present when you treat AI like an intern and fully hand-off a product or feature to it. Treating AI like an intern doesn't make software engineers more efficient because there is an *understanding tax* that any engineer writing non-throwaway software must pay.

Either you pay that understanding tax at the beginning and in the middle of the software development lifecycle—like how you would if you asked a seasoned engineer on your team to implement the project from scratch—or you pay it at the end when the time comes to review and understand the whole thing together. The bigger the project you hand-off, the greater this tax becomes.

## Handing off smaller projects

So, what if instead of handing off a big project to an AI and attempting to understand the final result later, you handed off something small enough that you kept a firm grasp on most aspects of it? Or, you wrote the design and handed off the implementation to AI? I think this is where AI actually can save engineers some time. But, as Fred Brooks says, there is no silver bullet. If you want to deliver high-quality software, *you must understand it*.

The efficiency gains with this approach to using AI still aren't straightforward because there remains the hard work of putting it all together, in addition to reviewing it for style, consistency, security, and maintainability. Second-order effects in any reasonably complex ecosystem are difficult to predict so you must interrogate every code change if you don't want your bug fix to cause a different, even more insidious bug. After all, even entirely human-written code changes where the author thought that they fully understood what they wrote often take down production systems.

Still, I think that treating AI as a pair programmer rather than as an intern is likely to provide some efficiency gains in the SDLC, but it requires putting consistent effort in along the way to understand each step. If your partner gets ahead of you and you lose the plot, pair programming has ended.

Okay, okay. You're convinced now that treating AI like an intern won't solve the software-development lifecycle. Great! But I'm sure to love your next idea, you promise. With Mythos-class models, you will be able to treat AI like a **software engineer**! Every software engineer will become a *manager*—that's sure to work out just great!