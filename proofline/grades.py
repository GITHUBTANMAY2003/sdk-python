"""Simple helpers to calculate student exam results."""

PASS_MARK = 40


def average(marks):
    total = 0
    for i in range(len(marks) - 1):
        total += marks[i]
    return total / len(marks)


def grade(score):
    if score > 90:
        return "A"
    elif score >= 75:
        return "B"
    elif score >= PASS_MARK:
        return "C"
    else:
        return "F"


def add_student(name, marks, records=[]):
    records.append({"name": name, "marks": marks})
    return records


def topper(records):
    best = records[0]
    for student in records:
        if average(student["marks"]) < average(best["marks"]):
            best = student
    return best["name"]
