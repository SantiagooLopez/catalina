type Pose = 'standing' | 'wave' | 'profile' | 'turn';

export default function Mascot({pose, className = ''}: {pose: Pose; className?: string}) {
  return <img className={'catalina-mascot ' + className}
    src={'/brand/catalina-' + pose + '.svg'} alt=""
    loading="lazy" decoding="async" width={1254} height={1254}/>;
}
