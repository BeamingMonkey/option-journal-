{% extends 'base.html' %}
{% block title %}Log Trade{% endblock %}
{% block content %}
<h2>Log New Trade</h2>
<form action="/log" method="post">
    <label>Symbol:</label><br>
    <input type="text" name="symbol" required><br><br>

    <label>Entry:</label><br>
    <input type="number" name="entry" step="0.01" required><br><br>

    <label>Exit:</label><br>
    <input type="number" name="exit" step="0.01" required><br><br>

    <label>Currency:</label><br>
    <select name="currency">
        <option value="USD">USD</option>
        <option value="EUR">EUR</option>
        <option value="INR">INR</option>
        <option value="GBP">GBP</option>
    </select><br><br>

    <label>Trade Quality:</label><br>
    <select name="quality">
        <option value="Good">Good</option>
        <option value="Neutral">Neutral</option>
        <option value="Poor">Poor</option>
    </select><br><br>

    <label>Reason:</label><br>
    <textarea name="reason" rows="4" cols="40"></textarea><br><br>

    <input type="submit" value="Log Trade">
</form>
<br>
<a href="/past">View Past Trades</a> |
<a href="/logout">Logout</a>
{% endblock %}