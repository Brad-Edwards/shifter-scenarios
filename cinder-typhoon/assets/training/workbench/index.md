# Dispatch rehearsal workbench

The outgoing operator left four work areas:

- [Handover repository](git/handover.git)
- [Delivery tracker export](workspace/delivery-tracker.csv)
- [Dispatch desk](http://workbench.training:8081/)
- [Retired courier client](retired-client/profile.json)
- [Diagnostic helper](http://workbench.training:8083/api/diagnostics/render?delivery_id=DL-204&view=public/DL-204.json)

The handover repository is read-only. Clone it with:

```text
git clone http://workbench.training:8080/git/handover.git
```

The current handover is only a blank replacement. Its ordinary repository
history was retained.
