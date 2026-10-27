class QuizRequired(ValueError):
    pass


class QuizRevisionChanged(ValueError):
    pass


def public_questions(items):
    return [{
        "id": item.id, "type": item.item_type, "question": item.question,
        "text": item.text, "options": list(item.options), "quiz_id": item.quiz_id,
        "quiz_title": item.quiz_title, "prerequisite": item.prerequisite,
        "pre_start": item.pre_start,
    } for item in items]


def evaluate_quiz(items, answers):
    if not isinstance(answers, dict) or len(answers) > 64:
        raise ValueError("Quiz answers exceed their limit")
    questions = {item.id: item for item in items if item.item_type != "preface"}
    if not questions:
        raise ValueError("This Lab has no quiz questions")
    if set(answers) - set(questions):
        raise ValueError("Answer refers to an unknown quiz question")
    normalized = {}
    for identifier, answer in answers.items():
        if type(answer) is not int or not 0 <= answer < len(questions[identifier].options):
            raise ValueError("Quiz answer is outside its options")
        normalized[identifier] = answer
    details = []
    outcomes = {}
    correct = 0
    graded = 0
    for question in items:
        if question.item_type == "preface":
            details.append({"id": question.id, "type": "preface", "quiz_id": question.quiz_id,
                            "text": question.text, "status": "PREFACE", "selected": None})
            continue
        selected = normalized.get(question.id)
        if question.prerequisite and outcomes.get(question.prerequisite, {}).get("status") == "CORRECT":
            status, feedback = "SKIPPED", ""
        elif question.answer is None:
            status, feedback = "UNASSESSED", ""
        elif selected is None:
            status, feedback = "UNANSWERED", ""
            graded += 1
        else:
            graded += 1
            status = "CORRECT" if selected == question.answer else "INCORRECT"
            correct += status == "CORRECT"
            feedback = (question.right_response if status == "CORRECT" else question.wrong_response) or question.explanation
        detail = {"id": question.id, "type": question.item_type, "quiz_id": question.quiz_id,
                  "status": status, "selected": selected, "explanation": feedback}
        if question.prerequisite:
            detail["prerequisite"] = question.prerequisite
        details.append(detail)
        outcomes[question.id] = detail
    def completed(identifiers):
        return all(outcomes[identifier]["status"] == "SKIPPED" or identifier in normalized
                   for identifier in identifiers)
    return {"answers": normalized, "questions": details, "correct": correct, "graded": graded,
            "passed": graded > 0 and correct == graded, "completed": completed(questions),
            "pre_start_completed": completed(identifier for identifier, item in questions.items() if item.pre_start)}


def requires_pre_start(items):
    return any(item.pre_start and item.item_type != "preface" for item in items)


def pre_start_answers(items, attempt):
    if not requires_pre_start(items):
        return None
    selected = {key: value for key, value in (attempt or {}).get("answers", {}).items()
                if any(item.id == key and item.pre_start for item in items)}
    if not evaluate_quiz(items, selected)["pre_start_completed"]:
        raise QuizRequired("Complete the preparation quiz for this Lab revision before starting; use cyberlab lab-quiz LAB")
    return selected


def session_report(session, answers, created_at):
    return {"format": "cyberlab-quiz/v1", "session_id": session.id,
            "lab_id": session.lab.metadata.id, "lab_version": session.lab.metadata.version,
            **evaluate_quiz(session.lab.quiz, answers), "created_at": created_at}
