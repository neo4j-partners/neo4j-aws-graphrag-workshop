---
title: "Vocareum Access"
weight: 2
---

## Step 1: Launch Your Environment

1. Sign into Vocareum using the link from your event invitation
2. Open the workshop lab and start it
3. Launch the hosted **Visual Studio Code** environment from the lab page

Vocareum provisions an AWS account for you and supplies its credentials to the lab environment.

When VS Code opens, select the **Python 3.10** interpreter shown below before
you run a notebook. Click the kernel or interpreter picker in the upper-right
corner of the notebook, then select that Python version.

::image[VS Code's Python interpreter picker with Python 3.10 selected]{src="../../../images/python-310.png" width=643}

:::alert{type="info" header="Where your AWS credentials come from"}
The lab environment carries the AWS credentials the notebooks use. You do not run `aws configure` and you do not paste an access key anywhere. Modules 4, 5, and 6 create AWS resources under that lab account, and everything lands in **us-east-1**.
:::

---

## Step 2: Open CONFIG.txt and the Notebooks

The lab already contains the workshop files. In the VS Code Explorer, open
`CONFIG.txt` at the workshop root, then open the `notebooks/` folder. You do
not need to clone the repository or install dependencies.

::image[VS Code Explorer with CONFIG.txt open in the preconfigured Vocareum workshop]{src="../../../images/vocareum-config.png" width=900}

---

## Step 3: Create Your Neo4j Database

The Vocareum lab does not include Neo4j. If you have not done it already, follow [Neo4j AuraDB Free Setup](../aura-free-setup/) to create an instance and restore the hotel graph into it. Come back here with the URI and password in hand.

---

## Step 4: Fill In CONFIG.txt

`CONFIG.txt` at the workshop root holds every setting the notebooks read. Replace the placeholder URI and password with the ones from your Aura instance\:

:::code{language=text}
NEO4J_URI=neo4j+s://xxxxxxxx.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_password_here
NEO4J_DATABASE=neo4j
:::

The username and the database name are already `neo4j`, which is what every Aura instance uses, so leave those two alone. If your instructor hands out a Bedrock API key at the start of class, uncomment the `AWS_BEARER_TOKEN_BEDROCK` line near the bottom of the file and paste the key after the equals sign. Otherwise leave that line commented out\: an uncommented but blank value is worse than no line at all, because it sends an empty Bearer header and Bedrock calls stop falling back to your normal AWS credentials. Paste the URI and password with no surrounding quotes and no trailing spaces, then save the file.

---

## Step 5: Verify the Environment

In the `notebooks/01-build-graph/` folder, open
`1.0_verify_environment.ipynb`. Confirm its kernel is still **Python 3.10** as
shown above, then run every cell. This notebook checks that the supplied
Vocareum credentials can reach the Bedrock models the workshop uses. It does
not create any resources.

When `1.0` completes successfully, stay in the same folder and open
`1.1_build_graph.ipynb` to begin Module 1. Run each later notebook with the
same **Python 3.10** interpreter selected.

:::alert{type="success" header="Ready"}
Proceed to [Module 1](../../01-build-graph/).
:::

---

## Troubleshooting

:::expand{header="Neo4j connection refused, or a connection timeout" defaultExpanded=false}
The Aura instance is not accepting connections yet. Open :link[the Aura console]{href="https://console.neo4j.io/" external=true} and look at the instance status. A newly created instance may still be provisioning, and an instance left idle for three days pauses and has to be resumed. Wait for **RUNNING**, then run the script again.
:::

:::expand{header="NoCredentialsError" defaultExpanded=false}
The terminal has no AWS credentials, which usually means the Vocareum lab session has expired or was never started. Return to the lab page, start the lab again, and open a fresh terminal so it picks up the new credentials.
:::

:::expand{header="Bedrock access denied" defaultExpanded=false}
Confirm you are in **us-east-1**. Amazon Nova 2 Multimodal Embeddings is an :link[Amazon Bedrock]{href="https://aws.amazon.com/bedrock/" external=true} model available only in that region. The Vocareum lab account has model access enabled for you, so no console changes are needed.
:::
