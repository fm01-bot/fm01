import { TeamType } from "@/_lib/Types";

export default function Team({ lang }: { lang: TeamType }) {
    return (
        <div id="team" className="h-screen">
            <p className="title">
                {lang.title}
            </p>
        </div>
    );
}