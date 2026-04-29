------------------------------ MODULE Captivity ------------------------------
EXTENDS Naturals, TLC

VARIABLES state

States == {"INIT", "PROBING", "PORTAL", "WAIT_USER", "AUTHENTICATING", "CONNECTED", "RETRY", "ERROR"}

TypeOK == state \in States

Init == state = "INIT"

\* Transitions
ProbeFromInit == 
    /\ state = "INIT"
    /\ state' = "PROBING"

ProbeResult == 
    /\ state = "PROBING"
    /\ \/ state' = "CONNECTED"
       \/ state' = "PORTAL"
       \/ state' = "ERROR"

PortalDetected == 
    /\ state = "PORTAL"
    /\ state' = "AUTHENTICATING"

AuthenticateResult == 
    /\ state = "AUTHENTICATING"
    /\ \/ state' = "CONNECTED"
       \/ state' = "WAIT_USER"
       \/ state' = "ERROR"

WaitUserTimeout == 
    /\ state = "WAIT_USER"
    /\ \/ state' = "RETRY"
       \/ state' = "PORTAL"
       \/ state' = "CONNECTED"

Retry == 
    /\ state = "RETRY"
    /\ state' = "PROBING"

ErrorRecovery == 
    /\ state = "ERROR"
    /\ state' = "RETRY"

Disconnect == 
    /\ state = "CONNECTED"
    /\ state' = "ERROR"

Next == 
    \/ ProbeFromInit
    \/ ProbeResult
    \/ PortalDetected
    \/ AuthenticateResult
    \/ WaitUserTimeout
    \/ Retry
    \/ ErrorRecovery
    \/ Disconnect

Spec == Init /\ [][Next]_state /\ WF_state(Next)

\* Safety Properties
NoInvalidState == state \in States

\* Liveness Properties
\* Eventually, the system must reach either CONNECTED or RETRY (from which it probes again)
EventuallyValid == <> (state = "CONNECTED" \/ state = "RETRY")

=============================================================================
