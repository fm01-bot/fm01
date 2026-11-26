"""A helper for converting stuff."""

from .regex import TIME

__all__ = ("seconds_to_text", "text_to_emoji", "text_to_seconds")


def text_to_seconds(time: str, base: int = 0) -> int:
	"""Converts text into seconds.

	Examples:
		>>> text_to_seconds("5m")  # 300
		>>> text_to_seconds("1d3min")  # 86400

	Args:
		time: String containing the time(s). Examples are:
			- 3min2s (3 minutes and 2 seconds) = 182 seconds
			- 5h30m (5 hours and 30 minutes) = 19000

			Supported time units:
			- years (365d)
			- months (31d)
			- weeks
			- days
			- hours
			- minutes
			- seconds
		base: Base seconds to add the result to, or remove the result from, if ``time`` starts with a plus or minus sign
			respectively.

	Returns:
		int: Seconds.

	Raises:
		ValueError: If the string doesn't contain time units.

	"""
	time_units = {
		"y": 60 * 60 * 24 * 365,
		"yr": 60 * 60 * 24 * 365,
		"yrs": 60 * 60 * 24 * 365,
		"year": 60 * 60 * 24 * 365,
		"years": 60 * 60 * 24 * 365,
		"mo": 60 * 60 * 24 * 31,
		"mos": 60 * 60 * 24 * 31,
		"month": 60 * 60 * 24 * 31,
		"months": 60 * 60 * 24 * 31,
		"w": 60 * 60 * 24 * 7,
		"wk": 60 * 60 * 24 * 7,
		"wks": 60 * 60 * 24 * 7,
		"week": 60 * 60 * 24 * 7,
		"weeks": 60 * 60 * 24 * 7,
		"d": 60 * 60 * 24,
		"dy": 60 * 60 * 24,
		"dys": 60 * 60 * 24,
		"day": 60 * 60 * 24,
		"days": 60 * 60 * 24,
		"h": 60 * 60,
		"hr": 60 * 60,
		"hrs": 60 * 60,
		"hour": 60 * 60,
		"hours": 60 * 60,
		"m": 60,
		"mn": 60,
		"mns": 60,
		"min": 60,
		"mins": 60,
		"minutes": 60,
		"s": 1,
		"sec": 1,
		"secs": 1,
		"seconds": 1,
	}

	raw_time = time.strip()
	is_negative = raw_time.startswith("-")
	is_positive = raw_time.startswith("+")
	to_parse = raw_time[1:].strip() if (is_negative or is_positive) else raw_time

	matches = list(TIME.finditer(to_parse))
	if not matches:
		try:
			val = int(to_parse)
			return base - val if is_negative else base + val
		except ValueError:
			raise ValueError(f"String doesn't contain time units ('{time}')")

	matched_chars = sum(m.end() - m.start() for m in matches)
	non_whitespace_chars = len("".join(to_parse.split()))
	if matched_chars != non_whitespace_chars:
		raise ValueError(f"Malformed time string with invalid trailing or embedded characters ('{time}')")

	total_seconds = 0
	for m in matches:
		value, unit = m.group(1), m.group(2)
		multiplier = time_units.get(unit)
		if multiplier is None:
			raise ValueError(f"Unknown time unit '{unit}' in '{time}'")
		total_seconds += int(value) * multiplier

	if is_negative:
		total_seconds = base - total_seconds
	elif is_positive or base:
		total_seconds = base + total_seconds

	return total_seconds


def seconds_to_text(seconds: int) -> str:
	"""Transforms seconds into an easily understandable representation.

	Examples:
		>>> seconds_to_text(300)  # 5 minutes
		>>> seconds_to_text(86400)  # 1 day

	Args:
		seconds: The number of seconds to be converted.

	Returns:
		str: A time format that is easy for humans to read.

	"""
	if seconds == 0:
		return "0s"
	time_units = {
		"y": 60 * 60 * 24 * 365,
		"mo": 60 * 60 * 24 * 31,
		"w": 60 * 60 * 24 * 7,
		"d": 60 * 60 * 24,
		"h": 60 * 60,
		"m": 60,
		"s": 1,
	}

	time = ""
	for unit, value in time_units.items():
		if seconds >= value:
			time += f"{seconds // value}{unit[0]} "
			seconds %= value

	return time.strip()


def text_to_emoji(text: str) -> list[str]:
	"""Converts a string to an emoji."""
	base = 0x1F1E6
	result = []
	for char in text.upper():
		if "A" <= char <= "Z":
			result.append(chr(base + ord(char) - ord("A")))
		else:
			result.append(char)
	return result
