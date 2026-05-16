export default function NewQuestionButton({ onClick }) {
  return (
    <button type="button" className="ooa-new-question" onClick={onClick}>
      + Ask another question
    </button>
  );
}
