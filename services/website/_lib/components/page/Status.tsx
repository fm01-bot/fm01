import { StatusType } from "@/_lib/Types";

export default function Status({ lang }: { lang: StatusType }) {
    return (
        <div id="status" className="h-screen">
            <p className="title">
                {lang.title}
            </p>
        </div>
    );
}