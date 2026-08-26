---
title: "Neo4j AuraDB Free Setup"
weight: 1
---

## Create the Database Every Module Talks To

Every module in this workshop reads and writes one :link[Neo4j]{href="https://neo4j.com/" external=true} graph. You create that database yourself on **Neo4j AuraDB Free** and restore the workshop's hotel graph into it. The database is the same on both compute paths, Vocareum and your own AWS account, so do this before you open a notebook.

---

## Step 1: Create an AuraDB Free Instance

1. Open :link[the Neo4j Aura console]{href="https://console.neo4j.io/" external=true} and sign in, or create a free account
2. Click **New Instance** and choose **AuraDB Free**
3. Name the instance and click **Create Instance**

:::alert{type="warning" header="Save the credentials the moment they appear"}
Aura generates the password and shows it once, at creation. It is never shown again. Click **Download and continue** to save the credentials file, or copy the password somewhere safe before you dismiss the dialog. If you lose it, reset the password from the instance's actions menu and use the new one.
:::

The credentials file names the values you paste into `CONFIG.txt` later\:

| Setting | Where it comes from |
|---|---|
| `NEO4J_URI` | The `NEO4J_URI` line, a `neo4j+s://` address ending in `.databases.neo4j.io` |
| `NEO4J_USERNAME` | `neo4j` |
| `NEO4J_PASSWORD` | The `NEO4J_PASSWORD` line from the same file |
| `NEO4J_DATABASE` | `neo4j`, which is the only database an Aura instance has |

Wait for the instance card to report **RUNNING**. A restore into an instance that is still provisioning fails.

---

## Step 2: Download the Workshop Graph

The hotel graph ships as a Neo4j database dump. Download it to the machine your browser is running on, not to the workshop compute environment, because the Aura console uploads it from that browser\:

:::code{language=text showCopyAction=true}
https://github.com/neo4j-partners/neo4j-aws-graphrag-workshop/raw/main/graph/neo4j-hotel-graph.dump
:::

The file is `neo4j-hotel-graph.dump`, a few megabytes. It is also in this repository at `graph/neo4j-hotel-graph.dump` if you have already cloned it locally.

---

## Step 3: Restore the Dump

1. On the instance card in the Aura console, open the more menu (`...`) and choose **Inspect**
2. Select the **Restore from backup file** tab, which sits next to **Snapshots**
3. Drag `neo4j-hotel-graph.dump` onto the upload area, or browse to it
4. Confirm the restore and wait for the instance to return to **RUNNING**

The tab accepts `.backup`, `.dump`, and `.tar` files, so the dump goes in as it downloaded.

:::alert{type="warning" header="A restore overwrites the instance"}
Restoring replaces everything already in the instance. That is why it is the first thing you do with a freshly created one. Do not restore over an instance you use for anything else.
:::

---

## Step 4: Confirm the Restore Landed

Open **Query** on the instance and run\:

:::code{language=cypher showCopyAction=true}
MATCH (hotel:Hotel {name: "AnyCompany Cairo Nile View"})
RETURN hotel.name AS name, hotel.address AS address
:::

One row comes back, and its address is `789 Corniche el-Nil, Cairo 11519, Egypt`.

That is the same check `environment/verify.py` runs later. It reads one hotel by name and compares the address rather than counting nodes, because a count is plausible at any value and a half-restored dump passes it.

---

## What the Restored Graph Deliberately Does Not Have

The dump holds the hotel corpus, extracted under the same extraction schema Module 1 explains. It does **not** hold the vector index, the full-text index, or five of the hotels. Module 1 creates both indexes and extracts those five hotels live, which is the point of that module. An instance with no indexes is the expected starting state, not a failed restore.

---

## Two Things to Know About the Free Tier

**An idle instance pauses.** AuraDB Free pauses an instance after three days without a connection. A paused instance refuses connections, which reads like a wrong URI. If you return to the workshop after a break, resume the instance from the console before running anything.

**The size limit is generous here.** AuraDB Free caps a graph at 200,000 nodes and 400,000 relationships. The workshop graph sits far under both, including everything Module 1 adds to it.

---

## Next

Take the URI, username, and password back to your setup path and paste them into `CONFIG.txt`\:

- [Vocareum Access](../vocareum-access/)
- [Own Account Setup](../own-account-setup/)
