# Udsendelse af orienteringsbrev om godkendelse af flyttesager.

This is a robot. Or rather an RPA, a Robotic Process Automation. The purpose of this robot is to send out letters to citizens, notifying them that their request for an address change has been approved.

To run, this robot needs a companion, or orchestrator. This robot is designed to work with the [OpenOrchestrator](https://github.com/itk-dev-rpa/OpenOrchestrator), a helpful tool to schedule and manage robots like this.
Within the database of the orchestrator, this robot will look for a set of credentials, which must be called **"Eflyt"**, used to log into the system that non-robot people use to approve requests for address changes, and which this robot knows how to use as well.

The robot is not very smart. Some cases are too complicated or sensitive for the robot to handle, and needs a real person to look after it. The robot doesn't even know this, but will just filter out some cases, if someone told it to look away.

When the robot finds a case that passes it's filter, it will also need to send a letter and save it for the great societal archives. This requires more credentials.
In the orchestrator, a **"Keyvault"** credential and **"Keyvault URI"** constant should contain the information the robot needs to look for a very secure store of certificates, needed to send letters digitally to citizens. With these, the letters will be safely sent and received.

Afterwards, the robot will finish its task by recording the letter in the Nova document and case palace, but only if it has access to a final set of credentials, called **"Nova API"**. Once it has access to all of these, it will happily look for people who are moving, and notify them that it is ok.
